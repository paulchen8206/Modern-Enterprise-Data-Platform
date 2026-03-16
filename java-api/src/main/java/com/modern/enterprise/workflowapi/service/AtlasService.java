package com.modern.enterprise.workflowapi.service;

import com.modern.enterprise.workflowapi.config.AppConfigProperties;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import org.springframework.stereotype.Service;

@Service
public class AtlasService extends HttpServiceClient {
  private final AppConfigProperties.Atlas cfg;

  public AtlasService(AppConfigProperties props, HttpClient httpClient) {
    super(httpClient);
    this.cfg = props.getAtlas();
  }

  public String registerLineage(String payload) throws Exception {
    // Atlas lineage endpoint is called directly so orchestration layers can stay thin.
    HttpRequest req = HttpRequest.newBuilder()
        .uri(URI.create(cfg.getEndpoint() + "/lineage"))
        .header("Authorization", basicAuth())
        .header("Content-Type", "application/json")
        .timeout(Duration.ofSeconds(30))
        .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
        .build();
    // Bubble up response details for easier operator troubleshooting.
    return executeOrThrow(req, "Atlas");
  }

  private String basicAuth() {
    String token = Base64.getEncoder().encodeToString((cfg.getUsername() + ":" + cfg.getPassword()).getBytes(StandardCharsets.UTF_8));
    return "Basic " + token;
  }
}
