"""
    Execute isso em uma migration customizada ou shell do Django
    
    python manage.py shell
    >>> from empresa.utils.popular_categorias import popular_categorias
    >>> popular_categorias()
"""
from empresa.models import CategoriaEmpresa


def popular_categorias():
    categorias = {
        "Comércio": {
            "descricao": "Empresas voltadas à venda de produtos e bens de consumo.",
            "subcategorias": {
                "Supermercado": "Estabelecimento de varejo que vende alimentos e produtos domésticos.",
                "Loja de Roupas": "Comércio especializado em vestuário e acessórios de moda.",
                "Material de Construção": "Loja que vende produtos para obras, reformas e construção civil.",
                "Papelaria": "Comércio de artigos escolares, de escritório e materiais de papel.",
                "Pet Shop": "Loja que vende produtos e serviços para animais de estimação.",
                "Loja de Eletrônicos": "Comércio de aparelhos eletrônicos como celulares, TVs e computadores."
            }
        },
        "Serviços": {
            "descricao": "Negócios focados na prestação de serviços para pessoas físicas ou jurídicas.",
            "subcategorias": {
                "Salão de Beleza": "Estabelecimento de cuidados pessoais, como cabelo e estética.",
                "Oficina Mecânica": "Serviços de manutenção e reparo de veículos automotores.",
                "Escritório de Contabilidade": "Serviços de contabilidade e assessoria fiscal para empresas.",
                "Consultoria": "Prestação de serviços especializados em diversas áreas.",
                "Serviços de TI": "Suporte, desenvolvimento e manutenção de sistemas e redes de tecnologia.",
                "Lavanderia": "Serviços de lavagem e cuidados com roupas e tecidos."
            }
        },
        "Indústria": {
            "descricao": "Empresas que transformam matéria-prima em produtos acabados.",
            "subcategorias": {
                "Fábrica de Alimentos": "Produção industrial de alimentos e bebidas.",
                "Metalúrgica": "Transformação de metais em peças ou estruturas.",
                "Indústria Têxtil": "Produção de tecidos, roupas e outros artigos de vestuário.",
                "Indústria Química": "Fabricação de produtos químicos para diversos setores."
            }
        },
        "Educação": {
            "descricao": "Instituições e empresas dedicadas ao ensino e formação.",
            "subcategorias": {
                "Escola Particular": "Instituições de ensino privadas de educação básica ou média.",
                "Curso de Idiomas": "Escolas especializadas no ensino de línguas estrangeiras.",
                "Centro de Treinamento Profissional": "Cursos voltados à capacitação técnica e profissional."
            }
        },
        "Saúde": {
            "descricao": "Empresas e instituições que prestam serviços relacionados à saúde.",
            "subcategorias": {
                "Clínica Médica": "Estabelecimento com atendimento ambulatorial em diversas especialidades.",
                "Laboratório de Análises": "Serviços de exames laboratoriais clínicos.",
                "Consultório Odontológico": "Serviços de atendimento e tratamento dentário.",
                "Farmácia": "Comércio de medicamentos e produtos de saúde."
            }
        },
        "Alimentação": {
            "descricao": "Negócios voltados à produção e venda de alimentos e refeições.",
            "subcategorias": {
                "Restaurante": "Serviço de refeições completas servidas no local.",
                "Lanchonete": "Venda de lanches e refeições rápidas.",
                "Cafeteria": "Estabelecimento especializado em café e acompanhamentos.",
                "Pizzaria": "Restaurante especializado em pizzas, servidas no local ou via delivery.",
                "Delivery de Comida": "Serviço de entrega de refeições, sem atendimento presencial."
            }
        },
        "Transporte e Logística": {
            "descricao": "Empresas que movimentam bens e pessoas ou gerenciam cadeias logísticas.",
            "subcategorias": {
                "Transportadora": "Empresa que realiza transporte de cargas.",
                "Motoboy": "Serviço de entregas rápidas com motocicletas.",
                "Frete e Mudanças": "Transporte de bens pessoais e mudanças residenciais ou comerciais.",
                "Logística de E-commerce": "Gestão de armazenamento e entrega para lojas virtuais."
            }
        },
        "Agronegócio": {
            "descricao": "Negócios ligados à produção agrícola, pecuária e agroindustrial.",
            "subcategorias": {
                "Fazenda": "Produção agrícola ou pecuária em áreas rurais.",
                "Cooperativa Agrícola": "Associação de produtores rurais para comercialização conjunta.",
                "Agroindústria": "Transformação de produtos do campo em bens de consumo ou industriais."
            }
        },
        "Tecnologia": {
            "descricao": "Empresas que desenvolvem soluções tecnológicas ou produtos digitais.",
            "subcategorias": {
                "Startup": "Empresa emergente de inovação com alto potencial de crescimento.",
                "Desenvolvedora de Software": "Criação de sistemas, apps e plataformas digitais.",
                "Empresa de Hardware": "Produção ou comércio de componentes e dispositivos eletrônicos.",
                "Consultoria em TI": "Serviços de análise, suporte e planejamento tecnológico."
            }
        },
        "Religião e Espiritualidade": {
            "descricao": "Instituições voltadas à prática religiosa e atividades espirituais.",
            "subcategorias": {
                "Igreja Evangélica": "Comunidade religiosa cristã de tradição evangélica.",
                "Igreja Católica": "Instituição da religião cristã católica apostólica romana.",
                "Templo Espírita": "Centro dedicado à doutrina espírita e práticas mediúnicas.",
                "Centro de Umbanda/Candomblé": "Espaço religioso para cultos de matrizes africanas.",
                "Outras Comunidades Religiosas": "Grupos de fé diversos, como budistas, mórmons, testemunhas de Jeová, etc."
            }
        },
        "ONGs e Instituições Sociais": {
            "descricao": "Organizações sem fins lucrativos voltadas a causas sociais.",
            "subcategorias": {
                "ONG Ambiental": "Organização voltada à preservação do meio ambiente.",
                "ONG Educacional": "Instituição que promove educação e capacitação.",
                "Instituição de Caridade": "Entidades que oferecem ajuda a comunidades carentes.",
                "Associação de Bairro": "Grupo organizado de moradores com fins comunitários.",
                "Projeto Social Independente": "Iniciativas não-governamentais de impacto social."
            }
        },
        "Esportes e Lazer": {
            "descricao": "Negócios ou entidades ligadas à prática de esportes e entretenimento.",
            "subcategorias": {
                "Academia de Ginástica": "Espaço para prática de exercícios físicos e musculação.",
                "Clube Esportivo": "Associação recreativa com atividades esportivas.",
                "Estúdio de Dança": "Espaço especializado em aulas e práticas de dança.",
                "Quadra ou Campo de Aluguel": "Locais para prática esportiva por hora.",
                "Empresa de Eventos e Festas": "Organização de eventos, festas e recreações."
            }
        },
        "Imobiliárias e Construção Civil": {
            "descricao": "Empresas que atuam no setor imobiliário e construção.",
            "subcategorias": {
                "Imobiliária": "Intermediação de compra, venda e aluguel de imóveis.",
                "Construtora": "Empresa responsável por obras e edificações.",
                "Incorporadora": "Planejamento e execução de empreendimentos imobiliários.",
                "Engenharia Civil": "Serviços de projeto e consultoria em obras.",
                "Arquitetura e Design de Interiores": "Projetos arquitetônicos e decoração de espaços."
            }
        },
        "Finanças e Seguros": {
            "descricao": "Empresas que atuam no setor financeiro ou de seguros.",
            "subcategorias": {
                "Corretora de Seguros": "Venda e administração de seguros pessoais ou empresariais.",
                "Financeira": "Crédito pessoal e empréstimos com ou sem garantia.",
                "Contabilidade e Escritório Fiscal": "Serviços contábeis e fiscais para empresas ou pessoas.",
                "Banco Digital": "Instituições financeiras 100% online.",
                "Cooperativa de Crédito": "Entidade financeira cooperativa com benefícios aos associados."
            }
        },
        "Mídia e Comunicação": {
            "descricao": "Empresas ou profissionais ligados à produção de conteúdo e divulgação.",
            "subcategorias": {
                "Agência de Publicidade": "Criação de campanhas de marketing e publicidade.",
                "Produtora de Vídeo": "Criação de conteúdo audiovisual profissional.",
                "Portal de Notícias": "Veículo de informação jornalística online ou impressa.",
                "Assessoria de Imprensa": "Intermediação de comunicação entre empresas e mídia.",
                "Influenciadores e Criadores de Conteúdo": "Profissionais que produzem conteúdo para redes sociais e plataformas digitais."
            }
        },
        "Turismo e Hotelaria": {
            "descricao": "Empresas que atuam na recepção, acomodação e transporte de turistas.",
            "subcategorias": {
                "Agência de Viagens": "Planejamento e venda de pacotes turísticos.",
                "Hotel ou Pousada": "Hospedagem para viajantes e turistas.",
                "Guia de Turismo": "Profissional licenciado para acompanhar e orientar turistas.",
                "Transporte Turístico": "Empresas que oferecem deslocamento para passeios turísticos.",
                "Aluguel por Temporada": "Imóveis residenciais alugados por curtos períodos."
            }
        }
    }

    for nome_categoria, dados in categorias.items():
        descricao_categoria = dados["descricao"]
        subcategorias = dados["subcategorias"]

        categoria_pai, _ = CategoriaEmpresa.objects.get_or_create(
            nome=nome_categoria,
            parent=None,
            defaults={"descricao": descricao_categoria}
        )

        # Atualiza a descrição se ela estiver vazia ou for diferente
        if not categoria_pai.descricao or categoria_pai.descricao != descricao_categoria:
            categoria_pai.descricao = descricao_categoria
            categoria_pai.save()

        for nome_sub, descricao_sub in subcategorias.items():
            subcategoria, _ = CategoriaEmpresa.objects.get_or_create(
                nome=nome_sub,
                parent=categoria_pai,
                defaults={"descricao": descricao_sub}
            )

            # Atualiza a descrição se necessário
            if not subcategoria.descricao or subcategoria.descricao != descricao_sub:
                subcategoria.descricao = descricao_sub
                subcategoria.save()
