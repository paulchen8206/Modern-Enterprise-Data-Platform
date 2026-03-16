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
public class CiService extends HttpServiceClient {
  private final AppConfigProperties.Github cfg;
  private final ObjectMapper mapper = new ObjectMapper();

  public CiService(AppConfigProperties props, HttpClient httpClient) {
    super(httpClient);
    this.cfg = props.getGithub();
  }

  public String triggerWorkflow(String wf, String branch) throws Exception {
    // Normalize base URL once to avoid malformed URLs when config omits trailing slash.
    String base = cfg.getActionsApi().endsWith("/") ? cfg.getActionsApi() : cfg.getActionsApi() + "/";
    String body = mapper.writeValueAsString(Map.of("ref", branch));
    HttpRequest req = HttpRequest.newBuilder()
        .uri(URI.create(base + wf + "/dispatches"))
        .header("Content-Type", "application/json")
        .header("Authorization", "Bearer " + cfg.getToken())
        .header("User-Agent", cfg.getUserAgent())
        .timeout(Duration.ofSeconds(30))
        .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
        .build();
    // Preserve upstream body for GitHub API diagnostics (permissions, workflow name, branch).
    return executeOrThrow(req, "GitHub workflow trigger");
  }
}
