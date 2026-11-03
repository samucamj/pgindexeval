"""pgIndexEval - Avaliador de estrategias de indexacao em PostgreSQL.

Produto Tecnico-Tecnologico (PTT) derivado da dissertacao sobre indexacao
em PostgreSQL. Automatiza a comparacao de cenarios de indice sobre uma carga
de consultas, medindo o tempo de execucao com EXPLAIN ANALYZE, aplicando
tratamento estatistico (desvio amostral, n-1) e recomendando a melhor
estrategia.

Tipo CAPES: T7 (Software/Aplicativo) - Grupo 4 - Nivel 3 (inovador).
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
