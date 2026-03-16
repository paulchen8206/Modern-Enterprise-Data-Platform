package com.modern.enterprise.workflowapi.exception;

public class UpstreamServiceException extends IntegrationException {
  private final int upstreamStatus;
  private final String upstreamBody;

  public UpstreamServiceException(String integration, int upstreamStatus, String upstreamBody) {
    super(integration, integration + " request failed with status " + upstreamStatus);
    this.upstreamStatus = upstreamStatus;
    this.upstreamBody = upstreamBody;
  }

  public int getUpstreamStatus() {
    return upstreamStatus;
  }

  public String getUpstreamBody() {
    return upstreamBody;
  }
}
