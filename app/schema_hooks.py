def remove_specific_paths(endpoints, **kwargs):
    filtered_endpoints = []

    for path, path_regex, method, callback in endpoints:
        view_module = callback.__module__

        if view_module.startswith('authentication.views') or view_module.startswith('empresa.views'):
            filtered_endpoints.append((path, path_regex, method, callback))

    return filtered_endpoints
