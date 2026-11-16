# HOTEL CESAR – Sistema Web de Gerenciamento Hoteleiro

Aplicação web completa desenvolvida com **Python e Django** como trabalho final da disciplina
de Desenvolvimento Web com Python e Django. O sistema reúne o **site institucional** do hotel
e uma **área administrativa** para gerenciar hóspedes, quartos, reservas, check-in, check-out e relatórios,
com todas as operações gravadas em banco de dados SQLite.

> Todos os dados de contato, hóspedes e reservas incluídos são **fictícios e demonstrativos**.

---

## Tecnologias utilizadas

- Python 3.10+ e Django 5 (arquitetura MTV)
- SQLite
- HTML5, CSS3 e JavaScript
- Bootstrap 5, Font Awesome 6 e Chart.js (via CDN – necessário acesso à internet para o visual completo)
- Pillow (upload de imagens dos quartos)

## Funcionalidades

**Site institucional (público)**
- Página inicial com banner, sobre o hotel, acomodações carregadas do banco, serviços, reserva e contato
- Páginas: Sobre, Acomodações, Fazer reserva e Contato
- Solicitação de reserva pelo visitante: o sistema verifica a disponibilidade de um quarto do tipo escolhido
  e registra a reserva com status **Pendente** (nunca confirma automaticamente)
- Formulário de contato com mensagens salvas no banco

**Sistema administrativo (restrito)**
- Login/logout com o sistema de autenticação do Django e proteção CSRF
- Dashboard com indicadores calculados no banco, reservas recentes, próximas chegadas/saídas,
  gráfico de ocupação e resumo financeiro
- Hóspedes: listar, pesquisar (nome/CPF), cadastrar, visualizar, editar e excluir (protegido por vínculos)
- Quartos: cards com filtros por status e tipo, cadastrar, visualizar, editar, alterar status e excluir
- Reservas: filtros por status, pesquisa, nova reserva com **resumo antes de salvar**, editar, confirmar,
  cancelar e consulta de disponibilidade
- Check-in: chegadas do dia, pesquisa por código/nome/CPF, confirmação de chegada
- Check-out: hóspedes hospedados, finalização e resumo da hospedagem para impressão
- Relatórios com filtro por data e exportação em **CSV**
- Configurações: dados da conta, troca de senha e mensagens de contato
- Django Admin personalizado ("Hotel Cesar Administração")

## Regras de negócio implementadas (validação no servidor)

- CPF obrigatório, **único** e com dígitos verificadores válidos; nome e telefone obrigatórios; e-mail validado
- Número do quarto único
- Data de saída posterior à data de entrada
- Quantidade de hóspedes limitada à capacidade do quarto
- Bloqueio de reservas com períodos conflitantes para o mesmo quarto (status Confirmada/Em andamento)
- Cálculo automático de diárias e valor total
- O **valor da diária é registrado no momento da reserva**; mudanças futuras no preço do quarto não alteram reservas antigas
- Check-in somente para reservas confirmadas, no período correto e com quarto disponível; impede check-in duplicado
- Check-out somente após o check-in; libera o quarto automaticamente
- Hóspedes e quartos com reservas vinculadas não podem ser excluídos (preserva o histórico)
- Faturamento **previsto** e de hospedagens **finalizadas** são exibidos separadamente; o sistema
  não registra pagamentos e deixa isso explícito nas telas

## Modelos e relacionamentos

```
Hospede (1) ──< (N) Reserva (N) >── (1) Quarto
```

| Model | Principais campos |
|-------|-------------------|
| `Hospede` | nome_completo, cpf, telefone, email, endereco, cidade, estado, data_nascimento, data_cadastro |
| `Quarto` | numero, tipo, descricao, capacidade, valor_diaria, status, imagem |
| `Reserva` | hospede (FK), quarto (FK), data_reserva, data_checkin, data_checkout, quantidade_hospedes, valor_diaria, valor_total, status, observacoes, checkin_realizado_em, checkout_realizado_em |
| `MensagemContato` | nome, email, telefone, assunto, mensagem, lida |

## Estrutura do projeto

```
hotel_cesar/
├── manage.py
├── requirements.txt
├── README.md
├── .gitignore
├── hotel_cesar/          # configurações (settings, urls, wsgi, asgi)
├── reservas/             # app principal
│   ├── models.py         # Hospede, Quarto, Reserva, MensagemContato
│   ├── views.py          # views (class-based) de todas as telas
│   ├── forms.py          # formulários com validação
│   ├── urls.py
│   ├── admin.py          # Django Admin personalizado
│   ├── tests.py          # testes automatizados
│   ├── validators.py     # validação de CPF e telefone
│   ├── mixins.py         # controle de acesso
│   ├── templatetags/     # filtros: moeda (R$), CPF, telefone
│   ├── management/commands/popular_demo.py
│   └── migrations/
├── templates/            # base, site, painel, hospedes/, quartos/, reservas/, checkin/, checkout/, relatorios/
└── static/               # css/, js/, images/
```

## Como instalar e executar

1. **Crie e ative um ambiente virtual**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux / macOS
   source venv/bin/activate
   ```

2. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute as migrações**
   ```bash
   python manage.py migrate
   ```

4. **Crie um superusuário (administrador)**
   ```bash
   python manage.py createsuperuser
   ```

5. **(Opcional) Insira os dados demonstrativos**
   ```bash
   python manage.py popular_demo
   ```
   Cria 10 quartos, 5 hóspedes e reservas sem conflitos (algumas chegando hoje, hóspedes em andamento,
   pendentes, finalizadas e uma cancelada), além dos grupos de acesso.
   Para também criar um usuário funcionário, informe uma senha sua:
   ```bash
   python manage.py popular_demo --limpar --funcionario recepcao --senha "EscolhaUmaSenhaForte"
   ```
   As datas são relativas ao dia em que o comando é executado. Use `--limpar` para recriar os dados.

6. **Inicie o servidor**
   ```bash
   python manage.py runserver
   ```

7. **Acesse**
   - Site do hotel: http://127.0.0.1:8000/
   - Login do sistema: http://127.0.0.1:8000/login/
   - Painel administrativo: http://127.0.0.1:8000/painel/
   - Django Admin: http://127.0.0.1:8000/django-admin/

## Perfis de acesso

| Perfil | Como obter | Acesso |
|--------|-----------|--------|
| Administrador | `createsuperuser` | Tudo, incluindo exclusões e Django Admin |
| Funcionário | grupo **Funcionários** (criado pelo `popular_demo`) ou `is_staff` | Painel completo: cadastrar, editar, reservas, check-in/out e relatórios. Exclusões exigem a permissão de excluir |
| Administradores (grupo) | grupo **Administradores** | Painel completo com permissão de exclusão |

Visitantes não autenticados são redirecionados para a tela de login ao tentar acessar o painel.
Usuários sem perfil de funcionário recebem "Acesso negado".

## Testes

```bash
python manage.py check
python manage.py test
```

Os testes cobrem: validação de CPF, CPF único, cálculo de diárias e valores, preço congelado,
datas inválidas, capacidade, conflito de reservas, fluxo de check-in/check-out, bloqueio de check-out
sem check-in, proteção de exclusão, controle de acesso, solicitação pública pendente, prévia de reserva,
exportação CSV e registro no Django Admin.

## Configuração para produção

O projeto usa variáveis de ambiente opcionais:

- `DJANGO_SECRET_KEY` – chave secreta (obrigatório trocar em produção)
- `DJANGO_DEBUG` – `0` para desativar o modo de depuração
- `DJANGO_ALLOWED_HOSTS` – hosts permitidos, separados por vírgula

Nenhuma senha real é armazenada no código.

## Publicação no GitHub

O projeto já possui `.gitignore` (ignora ambiente virtual, banco local, uploads e arquivos de ambiente).

```bash
git init
git add .
git commit -m "Hotel Cesar - sistema de gerenciamento hoteleiro"
git branch -M main
git remote add origin <URL_DO_SEU_REPOSITORIO>
git push -u origin main
```
