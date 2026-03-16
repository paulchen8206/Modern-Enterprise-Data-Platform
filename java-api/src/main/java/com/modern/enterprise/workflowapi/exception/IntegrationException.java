package com.modern.enterprise.workflowapi.exception;

public class IntegrationException extends RuntimeException {
  private final String integration;

  public IntegrationException(String integration, String message) {
    super(message);
    this.integration = integration;
  }

  public IntegrationException(String integration, String message, Throwable cause) {
    super(message, cause);
    this.integration = integration;
  }

  public String getIntegration() {
    return integration;
  }
}
