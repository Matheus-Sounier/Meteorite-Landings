# Meteorite Landings Pipeline

Pipeline para ler o CSV de meteoritos, validar e sinalizar problemas de qualidade, carregar os dados no PostgreSQL e disponibilizá-los para análise no Tableau.

O CSV é a entrada do pipeline. Os arquivos CSV/Parquet processados não são gerados; o Tableau deve consultar o banco.

## Requisitos

- Python 3.12
- Docker Desktop com Docker Compose
- Tableau Desktop com o conector/driver PostgreSQL instalado

## Configuração local

Se ainda não existir um `.env`, crie-o a partir do modelo. O comando abaixo preserva qualquer `.env` existente:

```powershell
if (-not (Test-Path .env)) {
	Copy-Item .env.example .env
}
```

Preencha as variáveis vazias de `.env` com a configuração do seu ambiente. O Compose e a conexão Python exigem as variáveis `POSTGRES_*`. `POSTGRES_HOST` deve apontar para o endereço acessível pelo processo Python; para execução diretamente no computador que hospeda o container, use o endereço local desse computador.

Não compartilhe nem faça commit do `.env`. Ele está listado em `.gitignore`. Use uma senha forte para o banco.

Ative o ambiente virtual Python 3.12 existente e instale as dependências:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Iniciar o PostgreSQL

Na raiz do projeto:

```powershell
docker compose up -d --wait
docker compose ps
```

Para acompanhar os logs do container:

```powershell
docker compose logs -f postgres
```

O banco usa um volume Docker nomeado, então os dados persistem ao parar o container. `docker compose down` para e remove o container, mas preserva o volume. **Não use `docker compose down -v` a menos que queira apagar os dados persistidos.**

## Executar o pipeline

Com o PostgreSQL ativo e o ambiente Python configurado:

```powershell
python -m meteorite_pipeline.application.cli
```

Sem argumento, o pipeline usa `data/raw/Meteorite_Landings.csv`. Para processar outro CSV compatível com o schema:

```powershell
python -m meteorite_pipeline.application.cli caminho\para\arquivo.csv
```

O pipeline normaliza os campos numéricos, valida as colunas, calcula flags de qualidade e atualiza estas tabelas:

- `meteorite_landings`: registros com as flags de qualidade.
- `data_quality_report`: contagens agregadas por métrica.

Cada execução substitui integralmente o conteúdo atual dessas tabelas dentro de uma transação. Não é uma carga incremental nem mantém histórico entre execuções.

## Conectar o Tableau

No Tableau Desktop, escolha o conector **PostgreSQL** e informe os valores correspondentes à configuração local:

- Servidor: endereço acessível do PostgreSQL, conforme `POSTGRES_HOST`.
- Porta: `POSTGRES_PORT`.
- Banco de dados: `POSTGRES_DB`.
- Usuário: `POSTGRES_USER` ou, preferencialmente, uma conta PostgreSQL dedicada de leitura.
- Senha: a credencial configurada para essa conta.

Selecione a tabela `meteorite_landings` para os dados detalhados e `data_quality_report` para as métricas agregadas. Para mapas, use `reclat` e `reclong`; consulte as flags `quality_missing_coordinates`, `quality_zero_coordinates`, `quality_invalid_latitude` e `quality_longitude_outside_range` para filtrar coordenadas inadequadas. As flags identificam problemas, mas não removem os registros.

O usuário `POSTGRES_USER` configurado na imagem oficial é o usuário inicial do banco. Para uso recorrente no Tableau, prefira criar uma conta separada com permissão somente de leitura. Se usar Tableau Server ou Tableau Cloud, `localhost` não aponta para o computador de desenvolvimento: configure um endpoint acessível e proteja o acesso ao banco com rede privada/firewall e credenciais de leitura.

## Testes

Testes unitários, sem conexão com PostgreSQL:

```powershell
python -m unittest tests.test_pipeline
```

Os testes de integração executam o pipeline e verificam as tabelas no PostgreSQL:

```powershell
python -m unittest tests.postgres_integration
```

**Atenção:** os testes de integração usam a conexão definida pelas variáveis de ambiente e o pipeline executa `TRUNCATE` nas tabelas antes de carregar os dados. Rode-os somente contra um banco descartável/de teste. Não aponte esses testes para o banco que o Tableau está usando.

A suíte integrada só executa quando `POSTGRES_TEST_DB` está definido e tem o mesmo valor de `POSTGRES_DB`. Para um teste local, configure ambos para o nome de um banco descartável já criado. Sem essa confirmação, a classe de integração é ignorada. O CI define a confirmação porque usa um PostgreSQL temporário.

O GitHub Actions executa os testes unitários e integrados em pushes para `main` e em pull requests direcionados a `main`. Configure as variáveis e o secret necessários conforme [docs/ci-configuration.md](docs/ci-configuration.md); o CI usa um PostgreSQL temporário.
