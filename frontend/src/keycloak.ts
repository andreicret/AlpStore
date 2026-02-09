import Keycloak, { KeycloakConfig } from "keycloak-js";

// Keycloak configuration
const config: KeycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: "alpstore",
  clientId: "alpstore-frontend",
};

const keycloak = new Keycloak(config);

export default keycloak;
