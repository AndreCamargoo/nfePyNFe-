"""
    python manage.py shell
    >>> from sistema.utils.popular_urls import popular_rotas  # ajuste o caminho
    >>> popular_rotas()
"""
from sistema.models import RotaSistema


def popular_rotas():
    urls_disponiveis = [
        # Sistema
        {
            "sistema": 3,
            "nome": "Listar sistemas disponíveis",
            "path": "/api/v1/sistemas/",
            "metodo": "GET",
            "descricao": "    Retorna uma lista de todos os sistemas cadastrados no sistema."
        },
        # Rotas do Sistema
        {
            "sistema": 3,
            "nome": "Listar rotas disponíveis por sistema",
            "path": "/api/v1/sistemas/rotas/",
            "metodo": "GET",
            "descricao": "Retorna todas as rotas e endpoints disponíveis para um sistema específico."
        },
        # Grupos de Permissões (ROTAS)
        {
            "sistema": 3,
            "nome": "Listar grupos de permissões da empresa",
            "path": "/api/v1/sistemas/grupos-rotas/",
            "metodo": "GET",
            "descricao": "Retorna todos os grupos de permissões criados pela empresa para gerenciar acesso de funcionários."
        },
        {
            "sistema": 3,
            "nome": "Criar novo grupo de permissões",
            "path": "/api/v1/sistemas/grupos-rotas/",
            "metodo": "POST",
            "descricao": "Cria um novo grupo de permissões para definir quais rotas os funcionários podem acessar."
        },
        {
            "sistema": 3,
            "nome": "Visualizar detalhes do grupo de permissões",
            "path": "/api/v1/sistema/grupo-rota/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os detalhes completos de um grupo de permissões específico."
        },
        {
            "sistema": 3,
            "nome": "Atualizar grupo de permissões",
            "path": "/api/v1/sistema/grupo-rota/<int:pk>/",
            "metodo": "PUT",
            "descricao": "Atualiza completamente as permissões de um grupo existente."
        },
        {
            "sistema": 3,
            "nome": "Atualização parcial do grupo",
            "path": "/api/v1/sistema/grupo-rota/<int:pk>/",
            "metodo": "PATCH",
            "descricao": "Atualiza apenas campos específicos do grupo de permissões."
        },
        {
            "sistema": 3,
            "nome": "Excluir grupo de permissões",
            "path": "/api/v1/sistema/grupo-rota/<int:pk>/",
            "metodo": "DELETE",
            "descricao": "Remove permanentemente um grupo de permissões do sistema."
        },
        # Categoria empresa
        {
            "sistema": 3,
            "nome": "Listar todas as categorias de empresas",
            "path": "/api/v1/categorias/",
            "metodo": "GET",
            "descricao": "Retorna a lista de categorias e subcategorias de empresas."
        },
        # Empresa
        {
            "sistema": 3,
            "nome": "Listar empresas do usuário",
            "path": "/api/v1/empresas/",
            "metodo": "GET",
            "descricao": "Retorna todas as empresas vinculadas ao usuário autenticado ou empresas que sejam filiais de alguma empresa pertencente ao usuário autenticado."
        },
        {
            "sistema": 3,
            "nome": "Criar empresa",
            "path": "/api/v1/empresas/",
            "metodo": "POST",
            "descricao": "Cria uma nova empresa vinculada ao usuário autenticado."
        },
        {
            "sistema": 3,
            "nome": "Detalhar empresa",
            "path": "/api/v1/empresa/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os dados de uma empresa específica."
        },
        {
            "sistema": 3,
            "nome": "Atualizar empresa",
            "path": "/api/v1/empresa/<int:pk>/",
            "metodo": "PUT",
            "descricao": "Atualiza todos os campos de uma empresa."
        },
        {
            "sistema": 3,
            "nome": "Atualizar empresa",
            "path": "/api/v1/empresa/<int:pk>/",
            "metodo": "PATCH",
            "descricao": "Atualiza parcialmente os campos de uma empresa."
        },
        {
            "sistema": 3,
            "nome": "Deletar empresa",
            "path": "/api/v1/empresa/<int:pk>/",
            "metodo": "DELETE",
            "descricao": "Remove uma empresa."
        },
        # Conexão banco de dados
        {
            "sistema": 3,
            "nome": "Listar conexão de banco",
            "path": "/api/v1/database/",
            "metodo": "GET",
            "descricao": "Retorna a configuração de conexão com o banco de dados da empresa matriz do usuário autenticado."
        },
        {
            "sistema": 3,
            "nome": "Criar conexão de banco",
            "path": "/api/v1/database/",
            "metodo": "POST",
            "descricao": "Cria uma nova configuração de conexão com banco de dados para a empresa matriz do usuário."
        },
        # Funcionarios
        {
            "sistema": 3,
            "nome": "Listar funcionários",
            "path": "/api/v1/funcionarios/",
            "metodo": "GET",
            "descricao": "Retorna todos os funcionários ativos das empresas vinculadas ao usuário autenticado."
        },
        {
            "sistema": 3,
            "nome": "Criar funcionário",
            "path": "/api/v1/funcionarios/",
            "metodo": "POST",
            "descricao": "Cria um novo funcionário vinculado a uma empresa do usuário autenticado."
        },
        {
            "sistema": 3,
            "nome": "Detalhar funcionário",
            "path": "/api/v1/funcionario/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os dados completos de um funcionário específico."
        },
        {
            "sistema": 3,
            "nome": "Atualizar funcionário",
            "path": "/api/v1/funcionario/<int:pk>/",
            "metodo": "PUT",
            "descricao": "Atualiza todos os campos de um funcionário."
        },
        {
            "sistema": 3,
            "nome": "Atualizar funcionário",
            "path": "/api/v1/funcionario/<int:pk>/",
            "metodo": "PATCH",
            "descricao": "Atualiza parcialmente os campos de um funcionário."
        },
        {
            "sistema": 3,
            "nome": "Desativar funcionário",
            "path": "/api/v1/funcionario/<int:pk>/",
            "metodo": "PATCH",
            "descricao": "Realiza soft delete (desativação) de um funcionário."
        },
        # Rotas permitidas funcionarios
        {
            "sistema": 3,
            "nome": "Listar rotas permitidas por funcionário",
            "path": "/api/v1/funcionarios/rotas/",
            "metodo": "GET",
            "descricao": "Retorna todas as rotas permitidas vinculadas aos funcionários das empresas que pertencem ao usuário autenticado."
        },
        {
            "sistema": 3,
            "nome": "Criar rota permitida para funcionário",
            "path": "/api/v1/funcionarios/rotas/",
            "metodo": "POST",
            "descricao": "Cria uma nova permissão de rota para um funcionário específico."
        },
        {
            "sistema": 3,
            "nome": "Detalhar rota permitida de funcionário",
            "path": "/api/v1/funcionario/rota/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os detalhes de uma rota permitida específica."
        },
        {
            "sistema": 3,
            "nome": "Atualizar rota permitida",
            "path": "/api/v1/funcionario/rota/<int:pk>/",
            "metodo": "PUT",
            "descricao": "Atualiza todos os campos de uma permissão de rota de funcionário."
        },
        {
            "sistema": 3,
            "nome": "Atualizar rota permitida",
            "path": "/api/v1/funcionario/rota/<int:pk>/",
            "metodo": "PATCH",
            "descricao": "Atualiza parcialmente os campos de uma permissão de rota de funcionário."
        },
        {
            "sistema": 3,
            "nome": "Remover rota permitida",
            "path": "/api/v1/funcionario/rota/<int:pk>/",
            "metodo": "DELETE",
            "descricao": "Remove uma permissão de rota de funcionário."
        },
        # [Allnube] NF
        {
            "sistema": 3,
            "nome": "Listar notas fiscais",
            "path": "/api/v1/nfes/",
            "metodo": "GET",
            "descricao": "Retorna uma lista paginada de notas fiscais da matriz e todas filiais com filtros avançados."
        },
        {
            "sistema": 3,
            "nome": "Listar notas fiscais da matriz",
            "path": "/api/v1/nfes/matriz/",
            "metodo": "GET",
            "descricao": "Retorna todas as notas fiscais da matriz."
        },
        {
            "sistema": 3,
            "nome": "Listar notas fiscais da matriz",
            "path": "/api/v1/nfes/filial/<int:documento>/",
            "metodo": "GET",
            "descricao": "Retorna notas fiscais de uma filial específica através do documento (CNPJ)."
        },
        {
            "sistema": 3,
            "nome": "Obter detalhes de uma nota fiscal",
            "path": "/api/v1/nfes/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os detalhes completos de uma nota fiscal específica."
        },
        # [Allnube] NF Produto
        {
            "sistema": 3,
            "nome": "Listar todos os produtos das notas fiscais",
            "path": "/api/v1/nfes/produtos/",
            "metodo": "GET",
            "descricao": "Retorna todos os produtos de todas as notas fiscais da matriz e suas filiais."
        },
        {
            "sistema": 3,
            "nome": "Listar produtos das notas fiscais da matriz",
            "path": "/api/v1/nfes/produtos/matriz/",
            "metodo": "GET",
            "descricao": "Retorna todos os produtos das notas fiscais da matriz."
        },
        {
            "sistema": 3,
            "nome": "Listar produtos das notas fiscais de uma filial",
            "path": "/api/v1/nfes/produtos/filial/<int:documento>/",
            "metodo": "GET",
            "descricao": "Retorna todos os produtos das notas fiscais de uma filial específica."
        },
        {
            "sistema": 3,
            "nome": "Obter detalhes completos de um produto",
            "path": "/api/v1/nfe/produto/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os detalhes completos de um produto específico incluindo todas as informações relacionadas."
        },
        # [Allnube] NF Fornecedores
        {
            "sistema": 3,
            "nome": "Listar todos os fornecedores",
            "path": "/api/v1/nfes/forncedor/",
            "metodo": "GET",
            "descricao": "Retorna todos os fornecedores (emitentes) das notas fiscais da matriz e suas filiais."
        },
        {
            "sistema": 3,
            "nome": "Listar fornecedores/emitentes da matriz",
            "path": "/api/v1/nfes/forncedor/matriz/",
            "metodo": "GET",
            "descricao": "Retorna todos os fornecedores (emitentes) das notas fiscais da matriz."
        },
        {
            "sistema": 3,
            "nome": "Listar fornecedores/emitentes de uma filial",
            "path": "/api/v1/nfes/forncedor/filial/<int:documento>/",
            "metodo": "GET",
            "descricao": "Retorna todos os fornecedores (emitentes) das notas fiscais de uma filial específica."
        },
        {
            "sistema": 3,
            "nome": "Obter detalhes completos de um fornecedor",
            "path": "/api/v1/nfes/forncedor/<int:pk>/",
            "metodo": "GET",
            "descricao": "Retorna os detalhes completos de um fornecedor/emitente específico."
        },
        # Processar lote de NFe / DANFE
        {
            "sistema": 3,
            "nome": "Processar lote de NFe",
            "path": "/api/v1/nfes/processar-lote/",
            "metodo": "GET",
            "descricao": "Processa um lote de arquivos XML de NFe, Eventos e Resumos contidos em um arquivo ZIP."
        },
        {
            "sistema": 3,
            "nome": "Gerar DANFE",
            "path": "/api/v1/nfes/gerar-danfe/<int:pk>/",
            "metodo": "GET",
            "descricao": "Gera o Documento Auxiliar da Nota Fiscal Eletrônica (DANFE) em formato PDF a partir do XML da NFe."
        },
    ]

    for dados in urls_disponiveis:
        rota, created = RotaSistema.objects.get_or_create(
            sistema_id=dados["sistema"],
            path=dados["path"],
            metodo=dados["metodo"],
            defaults={
                "nome": dados["nome"],
                "descricao": dados["descricao"]
            }
        )

        # Se a rota já existia, atualiza nome e descrição se necessário
        if not created:
            if rota.nome != dados["nome"] or rota.descricao != dados["descricao"]:
                rota.nome = dados["nome"]
                rota.descricao = dados["descricao"]
                rota.save()
