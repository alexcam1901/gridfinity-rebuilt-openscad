import { defineAuth } from "@aws-amplify/backend";

/**
 * Email sign-in. Single user today; the data model's owner-based auth already
 * isolates records per Cognito user, so adding household members later is an
 * invite + a group, not a schema change.
 */
export const auth = defineAuth({
  loginWith: { email: true },
});
