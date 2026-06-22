import { defineBackend } from "@aws-amplify/backend";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import { auth } from "./auth/resource";
import { data } from "./data/resource";
import { searchFn } from "./functions/search/resource";
import { storage } from "./storage/resource";

export const backend = defineBackend({
  auth,
  data,
  storage,
  searchFn,
});

// Grant the search function read access to the Item and Location DynamoDB tables.
// Amplify Gen 2 exposes generated table ARNs via backend.data.resources.tables.
const { tables } = backend.data.resources;
backend.searchFn.resources.lambda.addToRolePolicy(
  new PolicyStatement({
    actions: ["dynamodb:Scan", "dynamodb:Query"],
    resources: [
      tables["Item"].tableArn,
      `${tables["Item"].tableArn}/index/*`,
      tables["Location"].tableArn,
      `${tables["Location"].tableArn}/index/*`,
    ],
  })
);

// Pass table names to the Lambda via environment variables.
backend.searchFn.resources.lambda.addEnvironment(
  "ITEM_TABLE_NAME",
  tables["Item"].tableName
);
backend.searchFn.resources.lambda.addEnvironment(
  "LOCATION_TABLE_NAME",
  tables["Location"].tableName
);
