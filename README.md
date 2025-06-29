# Bot de Flashcards para Telegram - BotCard

Um bot de flashcards estilo Anki para Telegram, desenvolvido em Python, com funcionalidades para organizar perguntas e respostas categorizadas. Inclui servidor web simples para monitoramento de uptime.

---

## Funcionalidades

- Categorias personalizadas de flashcards
- Perguntas e respostas aleatórias
- Registro de acertos e erros por usuário
- Adicionar novas categorias e flashcards diretamente pelo chat
- Servidor web aiohttp integrado para responder ping (útil para UptimeRobot)
- Monitoramento automático de alterações no arquivo `flashcards.json`

---

## Tecnologias usadas

- Python 3.11+
- [python-telegram-bot](https://python-telegram-bot.org/) (v20+)
- [aiohttp](https://docs.aiohttp.org/en/stable/) (servidor web assíncrono)
- [watchdog](https://python-watchdog.readthedocs.io/en/stable/) (monitoramento de arquivos)
- `asyncio` e `nest_asyncio` (assincronismo)

---

## Como usar

### Pré-requisitos

- Python 3.11 ou superior
- Token do bot do Telegram (crie via [BotFather](https://telegram.me/BotFather))
- Instalar dependências com pip:

```bash
pip install python-telegram-bot aiohttp watchdog nest_asyncio
