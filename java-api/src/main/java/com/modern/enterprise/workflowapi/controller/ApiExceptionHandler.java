package com.modern.enterprise.workflowapi.controller;

import com.modern.enterprise.workflowapi.exception.IntegrationException;
import com.modern.enterprise.workflowapi.exception.UpstreamServiceException;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
  @ExceptionHandler(IllegalArgumentException.class)
  public ResponseEntity<Map<String, Object>> badRequest(IllegalArgumentException ex) {
    return problem(HttpStatus.BAD_REQUEST, ex.getMessage());
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<Map<String, Object>> validation(MethodArgumentNotValidException ex) {
    return problem(HttpStatus.BAD_REQUEST, "Invalid request payload");
  }

  @ExceptionHandler(IntegrationException.class)
  public ResponseEntity<Map<String, Object>> dependency(IntegrationException ex) {
    // Dependency failures are surfaced as 502 to distinguish them from API bugs.
    Map<String, Object> extras = new LinkedHashMap<>();
    extras.put("code", integrationCode(ex));
    extras.put("integration", ex.getIntegration());
    if (ex instanceof UpstreamServiceException upstream) {
      extras.put("upstreamStatus", upstream.getUpstreamStatus());
    }
    return problem(HttpStatus.BAD_GATEWAY, ex.getMessage(), extras);
  }

  @ExceptionHandler(IllegalStateException.class)
  public ResponseEntity<Map<String, Object>> illegalState(IllegalStateException ex) {
    return problem(HttpStatus.INTERNAL_SERVER_ERROR, ex.getMessage());
  }

  @ExceptionHandler(Exception.class)
  public ResponseEntity<Map<String, Object>> generic(Exception ex) {
    return problem(HttpStatus.INTERNAL_SERVER_ERROR, "Unexpected error");
  }

  private ResponseEntity<Map<String, Object>> problem(HttpStatus status, String detail) {
    return problem(status, detail, Map.of());
  }

  private ResponseEntity<Map<String, Object>> problem(
      HttpStatus status,
      String detail,
      Map<String, Object> extras) {
    // Use a stable response shape similar to RFC 7807 for client-side handling.
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("status", status.value());
    body.put("title", status.getReasonPhrase());
    body.put("detail", detail);
    body.putAll(extras);
    return ResponseEntity.status(status).body(body);
  }

  private String integrationCode(IntegrationException ex) {
    if (ex instanceof UpstreamServiceException) {
      return "INTEGRATION_UPSTREAM_ERROR";
    }
    return "INTEGRATION_CONNECTIVITY_ERROR";
  }
}
