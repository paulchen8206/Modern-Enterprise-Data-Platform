package com.modern.enterprise.workflowapi.service;

import com.modern.enterprise.workflowapi.exception.IntegrationConnectivityException;
import com.modern.enterprise.workflowapi.exception.UpstreamServiceException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public abstract class HttpServiceClient {
  private final HttpClient httpClient;

  protected HttpServiceClient(HttpClient httpClient) {
    this.httpClient = httpClient;
  }

  protected String executeOrThrow(HttpRequest request, String serviceName) throws Exception {
    try {
      HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() >= 300) {
        throw new UpstreamServiceException(serviceName, response.statusCode(), response.body());
      }
      return response.body();
    } catch (UpstreamServiceException ex) {
      throw ex;
    } catch (InterruptedException ex) {
      Thread.currentThread().interrupt();
      throw new IntegrationConnectivityException(serviceName, serviceName + " request was interrupted", ex);
    } catch (Exception ex) {
      throw new IntegrationConnectivityException(serviceName, serviceName + " connectivity failure", ex);
    }
  }

  protected boolean isReachable(HttpRequest request) {
    try {
      HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
      return response.statusCode() < 500;
    } catch (Exception ex) {
      return false;
    }
  }
}
