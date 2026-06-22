import { type ClientSchema, a, defineData } from "@aws-amplify/backend";
import { searchFn } from "../functions/search/resource";

/**
 * Inventory data model — multi-user-ready from day one.
 *
 * Every record uses owner-based authorization: Amplify stamps the signed-in
 * Cognito user as the owner and auto-filters all reads/writes by it, so a
 * single account gets correct isolation for free. `householdId` is present on
 * every model now (unused while solo) so the migration to a shared household is
 * a rule swap — `allow.owner()` -> `allow.groupDefinedIn("householdId")` plus a
 * Cognito group per household — with no data reshape. GSIs are keyed on
 * householdId so per-household queries are already scoped.
 */
const schema = a.schema({
  Location: a
    .model({
      name: a.string().required(),
      type: a.enum(["room", "shelf", "cabinet", "drawer", "bin", "other"]),
      parentId: a.id(), // self-reference -> arbitrary-depth hierarchy
      parent: a.belongsTo("Location", "parentId"),
      children: a.hasMany("Location", "parentId"),
      notes: a.string(),
      householdId: a.id(), // reserved for multi-user; unused while solo
      items: a.hasMany("Item", "locationId"),
    })
    .secondaryIndexes((index) => [index("householdId")])
    .authorization((allow) => [allow.owner()]),

  Item: a
    .model({
      name: a.string().required(),
      quantity: a.integer().default(1),
      tags: a.string().array(),
      ocrText: a.string(),
      locationId: a.id(),
      location: a.belongsTo("Location", "locationId"),
      primaryPhotoId: a.id(),
      gridfinityRef: a.string(), // optional loose link to a designed bin
      householdId: a.id(),
      photos: a.hasMany("Photo", "itemId"),
    })
    .secondaryIndexes((index) => [
      index("householdId"),
      index("locationId"),
    ])
    .authorization((allow) => [allow.owner()]),

  Photo: a
    .model({
      s3Key: a.string().required(),
      itemId: a.id(),
      item: a.belongsTo("Item", "itemId"),
      modelUsed: a.string(), // which vision model identified this photo
      modelName: a.string(),
      rekText: a.string(),
      takenAt: a.datetime(),
      householdId: a.id(),
    })
    .secondaryIndexes((index) => [index("itemId")])
    .authorization((allow) => [allow.owner()]),

  // Custom type returned by the searchItems query.
  SearchResult: a.customType({
    id: a.string(),
    name: a.string(),
    location: a.string(),
    quantity: a.integer(),
    score: a.float(),
  }),

  // Synonym-aware search across name, tags, and OCR text. Backed by the
  // `search` Lambda which replicates the Python query/handler.py logic in
  // TypeScript (so it runs inside Amplify AppSync without a Python layer).
  searchItems: a
    .query()
    .arguments({ query: a.string().required() })
    .returns(a.ref("SearchResult").array())
    .handler(a.handler.function(searchFn))
    .authorization((allow) => [allow.authenticated()]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: { defaultAuthorizationMode: "userPool" },
});
