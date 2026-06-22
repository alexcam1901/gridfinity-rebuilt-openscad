import { defineStorage } from "@aws-amplify/backend";

/**
 * Item photos. Each user can only touch objects under their own
 * identity-scoped prefix, matching the owner-based data isolation.
 */
export const storage = defineStorage({
  name: "itemPhotos",
  access: (allow) => ({
    "photos/{entity_id}/*": [
      allow.entity("identity").to(["read", "write", "delete"]),
    ],
  }),
});
