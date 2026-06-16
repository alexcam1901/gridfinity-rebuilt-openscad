import { defineFunction } from "@aws-amplify/backend";

export const searchFn = defineFunction({
  name: "search-items",
  entry: "./handler.ts",
  environment: {
    // Table names are injected by Amplify at deploy time via SSM / CDK outputs.
    // The backend.ts override below grants DynamoDB read access.
  },
});
