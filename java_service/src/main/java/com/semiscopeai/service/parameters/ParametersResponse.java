package com.semiscopeai.service.parameters;

import java.util.List;
import java.util.Map;

public record ParametersResponse(Map<String, List<String>> options, Map<String, String> defaults) {}
