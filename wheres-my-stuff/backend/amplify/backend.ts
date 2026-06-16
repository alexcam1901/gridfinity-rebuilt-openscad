import { defineBackend } from "@aws-amplify/backend";
import { auth } from "./auth/resource";
import { data } from "./data/resource";
import { storage } from "./storage/resource";

/**
 * Amplify Gen 2 backend entry point.
 *
 * The vision (ingest-photo) and search (query) handlers live under
 * backend/functions/ as Python Lambdas (so they can share shared/synonyms.json
 * with the eval harness). Wire them in here as custom function resources /
 * AppSync resolvers once the Python build step is set up — see README.
 */
export const backend = defineBackend({
  auth,
  data,
  storage,
});
