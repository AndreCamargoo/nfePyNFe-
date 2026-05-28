def remove_specific_paths(endpoints, **kwargs):
    """
    Inclui apenas views específicas que queremos documentar.
    """
    allowed_views = {
        # Autenticação
        'CustomTokenObtainAPIView', 'CustomTokenRefreshAPIView', 'LogoutView',

        # Gestão de usuários
        'UserProfileCreateView', 'PasswordResetRequestAPIView', 'PasswordResetConfirmAPIView',

        # Perfil
        'UserProfileView', 'UserUpdateProfile', 'UserPermissionsView',

        # Sistemas
        'SistemaListCreateAPIView',

        # Rotas disponiveis de acordo com o sistema
        'RotaSistemaListCreateAPIView',

        # Categoria das empresas
        'CategoriaEmpresaListCreateAPIView',

        # Cadastro empresa
        'EmpresaListCreateAPIView', 'EmpresaRetrieveUpdateDestroyAPIView',

        # Cadastro empresa conexão
        'ConexaoBancoListCreateAPIView',

        # Cadastro empresa funcionarios
        'FuncionarioListCreateAPIView', 'FuncionarioRetrieveUpdateDestroyAPIView',

        # Cadastro empresa permissão de navegação
        'FuncionarioRotasListCreateAPIView', 'FuncionarioRotasRetrieveUpdateDestroyAPIView',

        # Cadastrar grupo de rotas de acesso a funcionarios
        'GrupoRotaSistemaListCreateAPIView', 'GrupoRotaSistemaRetrieveUpdateDestroyAPIView',

        # Notas fiscais completas
        'NfeListCreateAPIView', 'ProcessarLoteNFeAPIView', 'GerarDanfeAPIView',
        'NfeListMatrizAPIView', 'NfeListFilialAPIView', 'NfeRetrieveUpdateDestroyAPIView',

        # Notas fisica (produtos)
        'NfeTodosProdutosListAPIView', 'NfeProdutosMatrizListAPIView',
        'NfeProdutosFilialListAPIView', 'NfeProdutoRetrieveAPIView',

        # Nota fiscal (fornecedores)
        'NfeTodosFornecedorListAPIView', 'NfeFornecedorMatrizListAPIView',
        'NfeFornecedorFilialListAPIView', 'NfeFornecedorRetrieveAPIView',
    }

    filtered_endpoints = []

    for path, path_regex, method, callback in endpoints:
        # Verifica se é uma view que queremos documentar
        view_name = getattr(callback, 'cls').__name__ if hasattr(callback, 'cls') else None

        if view_name in allowed_views:
            filtered_endpoints.append((path, path_regex, method, callback))

    return filtered_endpoints