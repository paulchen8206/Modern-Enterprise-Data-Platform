package com.modern.enterprise.workflowapi.exception;

public class IntegrationConnectivityException extends IntegrationException {
  public IntegrationConnectivityException(String integration, String message, Throwable cause) {
    super(integration, message, cause);
  }
}
