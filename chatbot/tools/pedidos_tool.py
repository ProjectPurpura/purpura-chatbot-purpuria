import json
import psycopg2
from langchain.tools import tool
from common.env import ENV

# FUNÇÃO DE EXECUÇÃO AUXILIAR

def execute_sql_and_return_json(sql: str) -> str:
    """Executa consultas no PostgreSQL e retorna resultados como JSON."""
    conn = None
    try:
        conn = psycopg2.connect(ENV.POSTGRES_URL)
        cur = conn.cursor()
        cur.execute(sql)
        
        colnames = [desc[0] for desc in cur.description]
        results = [dict(zip(colnames, row)) for row in cur.fetchall()]
        
        cur.close()
        # Retorna o JSON
        return json.dumps(results, indent=2, default=str)

    except psycopg2.Error as e:
        return f"ERRO_DB_POSGRES: Falha ao executar consulta. Detalhes: {e}"
    except Exception as e:
        return f"ERRO_GERAL_POSGRES: {e}"
    finally:
        if conn:
            conn.close()

# --- TOOLS ---

@tool
def consultar_pedidos_usuario(user_id: str, status: str = 'aprovado,pendente') -> str:
    """
    Busca a lista de pedidos ATIVOS onde o usuário é o VENDEDOR (fkEntregador), filtrando por status.
    Args:
        user_id: O ID de identificação do usuário (fkEntregador/CNPJ). OBRIGATÓRIO.
        status: Status dos pedidos ('pendente', 'aprovado', 'concluído', 'cancelado'). Separe por vírgulas.
    Retorna: Um JSON com os dados dos pedidos (idPedido, status, agendamentoColeta, valorTotal).
    """
    safe_status = ','.join([f"'{s.strip()}'" for s in status.split(',') if s.strip()])

    sql = f"""
    SELECT idPedido, agendamentoColeta, status, valorTotal
    FROM pedido
    WHERE fkEntregador = '{user_id}' AND status IN ({safe_status})
    ORDER BY agendamentoColeta DESC;
    """
    return execute_sql_and_return_json(sql)

@tool
def obter_pedido_mais_antigo(user_id: str) -> str:
    """
    Retorna o ID, data e valor do pedido mais antigo com status 'pendente' ou 'aprovado' para o VENDEDOR (user_id).
    Essencial para o roteamento duplo (Pedidos -> Resíduos).
    Args:
        user_id: O ID de identificação do usuário (fkEntregador/CNPJ). OBRIGATÓRIO.
    Retorna: Um JSON com o ID, data e valor do pedido.
    """
    sql = f"""
    SELECT idPedido, data, valorTotal
    FROM pedido
    WHERE fkEntregador = '{user_id}' AND status IN ('pendente', 'aprovado')
    ORDER BY data ASC
    LIMIT 1;
    """
    return execute_sql_and_return_json(sql)

@tool
def consultar_transporte_pedido(pedido_id: int, user_id: str) -> str:
    """
    Consulta o transportador e a data de retirada de um pedido específico, validando a posse do VENDEDOR.
    Args:
        pedido_id: O ID do pedido (fkPedido). OBRIGATÓRIO.
        user_id: O ID do usuário para validação de posse (fkEntregador/CNPJ). OBRIGATÓRIO.
    Retorna: Um JSON com os detalhes do transporte.
    """
    sql = f"""
    SELECT t.transportadora, t.dataRetirada
    FROM transporte t
    INNER JOIN pedido p ON t.fkPedido = p.idPedido
    WHERE t.fkPedido = {pedido_id} AND p.fkEntregador = '{user_id}';
    """
    return execute_sql_and_return_json(sql)

@tool
def consultar_pedidos_comprados(user_id: str, status: str = 'aprovado,pendente') -> str:
    """
    Busca a lista de pedidos ATIVOS onde o usuário é o COMPRADOR (fkRecebedor), filtrando por status.
    Args:
        user_id: O ID de identificação do usuário (fkRecebedor/CNPJ). OBRIGATÓRIO.
        status: Status dos pedidos ('pendente', 'aprovado', 'concluído', 'cancelado'). Separe por vírgulas.
    Retorna: Um JSON com os dados dos pedidos comprados.
    """
    safe_status = ','.join([f"'{s.strip()}'" for s in status.split(',') if s.strip()])

    sql = f"""
    SELECT idPedido, agendamentoColeta, status, valorTotal, fkEntregador as Vendedor
    FROM pedido
    WHERE fkRecebedor = '{user_id}' AND status IN ({safe_status})  -- <<< CORREÇÃO AQUI (fkComprador -> fkRecebedor)
    ORDER BY agendamentoColeta DESC;
    """
    return execute_sql_and_return_json(sql)

@tool
def consultar_pedidos_geral(user_id: str, min_data: str = None, max_data: str = None, min_valor: float = None, max_valor: float = None) -> str:
    """
    Consulta todos os pedidos do usuário (VENDEDOR ou COMPRADOR), permitindo filtragem opcional por
    intervalo de DATA (formato YYYY-MM-DD) e/ou VALOR.
    
    Args:
        user_id: O ID de identificação do usuário (CNPJ). OBRIGATÓRIO.
        min_data: Data mínima da compra (ex: '2024-01-01'). Não obrigatório.
        max_data: Data máxima da compra (ex: '2024-12-31'). Não obrigatório.
        min_valor: Valor mínimo para o pedido. Não obrigatório.
        max_valor: Valor máximo para o pedido. Não obrigatório.
    Retorna: Um JSON com os pedidos que correspondem aos critérios.
    """
    
    # 1. Cláusula WHERE base: ser Vendedor OU Recebedor (Comprador)
    where_clause = f"WHERE fkEntregador = '{user_id}' OR fkRecebedor = '{user_id}'"  # <<< CORREÇÃO AQUI (fkComprador -> fkRecebedor)
    
    # 2. Adiciona filtros opcionais de DATA
    if min_data:
        where_clause += f" AND data >= '{min_data}'"
    if max_data:
        where_clause += f" AND data <= '{max_data}'"

    # 3. Adiciona filtros opcionais de VALOR
    if min_valor is not None:
        where_clause += f" AND valorTotal >= {min_valor}"
    if max_valor is not None:
        where_clause += f" AND valorTotal <= {max_valor}"

    # 4. Constrói o SQL completo
    sql = f"""
    SELECT idPedido, data, agendamentoColeta, status, valorTotal, fkEntregador, fkRecebedor  -- <<< CORREÇÃO AQUI (fkComprador -> fkRecebedor)
    FROM pedido
    {where_clause}
    ORDER BY data DESC;
    """
    return execute_sql_and_return_json(sql)


PEDIDOS_TOOLS = [
    consultar_pedidos_usuario, 
    obter_pedido_mais_antigo, 
    consultar_transporte_pedido,
    consultar_pedidos_comprados, 
    consultar_pedidos_geral
]