import { FoundationStatus } from "../components/foundation-status";
import { loadWebEnvironment } from "../config/environment";
import { fetchApiHealth } from "../lib/api/health-client";

export default async function HomePage() {
  const environment = loadWebEnvironment();
  const api = await fetchApiHealth(environment.apiBaseUrl);
  return (
    <FoundationStatus
      environment={environment.applicationEnvironment}
      api={api}
      apiBaseUrl={environment.browserApiBaseUrl.toString()}
    />
  );
}
