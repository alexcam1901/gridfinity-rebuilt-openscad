/**
 * AppSync custom query resolver: searchItems(query: String!): [SearchResult]
 *
 * Synonym-aware ranked search across item name, tags, and OCR text.
 * Mirrors the Python logic in backend/functions/query/handler.py so the
 * same algorithm runs in both the Amplify-managed Lambda (this file) and
 * the standalone Python Lambda for local/eval use.
 *
 * DynamoDB tables are accessed via environment variables injected by Amplify:
 *   ITEM_TABLE_NAME   – the Amplify-generated Item table
 *   LOCATION_TABLE_NAME – the Amplify-generated Location table
 * The backend.ts CDK escape-hatch grants Scan + Query on both tables.
 */

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand } from "@aws-sdk/lib-dynamodb";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({}));

// ---------------------------------------------------------------------------
// Synonym groups — shared source of truth is shared/synonyms.json; these are
// bundled here at build time. Update both when the synonym map changes.
// ---------------------------------------------------------------------------
const SYNONYM_GROUPS: string[][] = [
  ["wire nuts", "wire connectors", "twist caps", "wire caps"],
  ["zip ties", "cable ties", "zap straps", "tie wraps"],
  ["duct tape", "duck tape", "gorilla tape"],
  ["screws", "bolts", "fasteners"],
  ["drill bits", "drill bit set", "bit set"],
  ["extension cord", "power cord", "extension lead"],
  ["batteries", "battery", "alkaline"],
  ["tape measure", "measuring tape", "ruler"],
];

const STOPWORDS = new Set([
  "where", "are", "is", "my", "the", "a", "an", "do", "i", "have", "find", "get",
]);

// ---------------------------------------------------------------------------
// Normalisation + synonym expansion
// ---------------------------------------------------------------------------

function normalize(term: string): string {
  const t = term.toLowerCase().replace(/[^a-z0-9 ]+/g, " ");
  return t
    .split(" ")
    .filter(Boolean)
    .map((w) => {
      if (w.length > 3 && w.endsWith("es")) {
        const stem = w.slice(0, -2);
        if (/(?:s|x|z|ch|sh)$/.test(stem)) return stem;
      }
      if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss")) {
        return w.slice(0, -1);
      }
      return w;
    })
    .join(" ");
}

const termToGroup = new Map<string, number>();
SYNONYM_GROUPS.forEach((group, gid) => {
  group.forEach((term) => termToGroup.set(normalize(term), gid));
  // Also index individual words within each phrase
  group.forEach((term) =>
    normalize(term)
      .split(" ")
      .forEach((w) => {
        if (!termToGroup.has(w)) termToGroup.set(w, gid);
      })
  );
});

function expandTerm(term: string): Set<string> {
  const n = normalize(term);
  const expanded = new Set<string>([n]);
  const gid = termToGroup.get(n);
  if (gid !== undefined) {
    termToGroup.forEach((g, t) => {
      if (g === gid) expanded.add(t);
    });
  }
  return expanded;
}

function queryTerms(query: string): string[] {
  return normalize(query)
    .split(" ")
    .filter((w) => w && !STOPWORDS.has(w));
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

function score(
  item: Record<string, unknown>,
  terms: string[]
): number {
  const nameTokens = new Set(normalize(String(item.name ?? "")).split(" "));
  const tagTokens = new Set(
    ((item.tags as string[]) ?? []).flatMap((t: string) =>
      normalize(t).split(" ")
    )
  );
  const ocrTokens = new Set(normalize(String(item.ocrText ?? "")).split(" "));

  let s = 0;
  for (const term of terms) {
    const variants = expandTerm(term);
    const inName = [...variants].some((v) => nameTokens.has(v));
    const inTag = [...variants].some((v) => tagTokens.has(v));
    const inOcr = [...variants].some((v) => ocrTokens.has(v));
    if (inName) s += 3.0;
    else if (inTag) s += 1.5;
    else if (inOcr) s += 1.0;
  }
  return terms.length > 0 ? s / terms.length : 0;
}

// ---------------------------------------------------------------------------
// Location breadcrumb
// ---------------------------------------------------------------------------

function breadcrumb(
  item: Record<string, unknown>,
  locById: Map<string, Record<string, unknown>>
): string {
  const parts: string[] = [];
  let cur = locById.get(String(item.locationId ?? ""));
  const seen = new Set<string>();
  while (cur && !seen.has(String(cur.id))) {
    seen.add(String(cur.id));
    parts.unshift(String(cur.name ?? "?"));
    cur = locById.get(String(cur.parentId ?? ""));
  }
  return parts.join(" > ");
}

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

export const handler = async (event: {
  arguments: { query: string };
  identity?: { sub?: string };
}) => {
  const { query } = event.arguments;
  const owner = event.identity?.sub ?? "";

  const itemTable = process.env.ITEM_TABLE_NAME ?? "";
  const locTable = process.env.LOCATION_TABLE_NAME ?? "";

  const [itemsRes, locsRes] = await Promise.all([
    ddb.send(
      new ScanCommand({
        TableName: itemTable,
        FilterExpression: "#own = :owner",
        ExpressionAttributeNames: { "#own": "owner" },
        ExpressionAttributeValues: { ":owner": owner },
      })
    ),
    ddb.send(
      new ScanCommand({
        TableName: locTable,
        FilterExpression: "#own = :owner",
        ExpressionAttributeNames: { "#own": "owner" },
        ExpressionAttributeValues: { ":owner": owner },
      })
    ),
  ]);

  const items = (itemsRes.Items ?? []) as Record<string, unknown>[];
  const locById = new Map(
    ((locsRes.Items ?? []) as Record<string, unknown>[]).map((l) => [
      String(l.id),
      l,
    ])
  );

  const terms = queryTerms(query);
  const scored = items
    .map((item) => ({ item, s: score(item, terms) }))
    .filter(({ s }) => s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, 10)
    .map(({ item, s }) => ({
      id: item.id,
      name: item.name,
      location: breadcrumb(item, locById),
      quantity: item.quantity ?? null,
      score: Math.round(s * 1000) / 1000,
    }));

  return scored;
};
