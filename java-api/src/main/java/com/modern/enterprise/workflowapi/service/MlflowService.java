package com.modern.enterprise.workflowapi.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.modern.enterprise.workflowapi.config.AppConfigProperties;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class MlflowService extends HttpServiceClient {
  private final AppConfigProperties.Mlflow cfg;
  private final ObjectMapper mapper = new ObjectMapper();

  public MlflowService(AppConfigProperties props, HttpClient httpClient) {
    super(httpClient);
    this.cfg = props.getMlflow();
  }

  public String createRun(String experimentId, String runName) throws Exception {
    // Keep payload minimal; additional tags/params can be logged later via MLflow APIs.
    String body = mapper.writeValueAsString(Map.of("experiment_id", experimentId, "run_name", runName));
    HttpRequest req = HttpRequest.newBuilder()
        .uri(URI.create(cfg.getTrackingUri() + "/api/2.0/mlflow/runs/create"))
        .header("Content-Type", "application/json")
        .timeout(Duration.ofSeconds(cfg.getRequestTimeoutSeconds()))
        .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
        .build();
    return executeOrThrow(req, "MLflow");
  }

  public boolean canReachMlflow() {
    // Base tracking URI is sufficient for liveness checks in local deployments.
    HttpRequest req = HttpRequest.newBuilder().uri(URI.create(cfg.getTrackingUri()))
        .timeout(Duration.ofSeconds(cfg.getRequestTimeoutSeconds())).GET().build();
    return isReachable(req);
  }
}
