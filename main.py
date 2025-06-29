from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from aiohttp import web
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading, random, json, unicodedata, re, difflib, os, asyncio, nest_asyncio

# Dicionários globais para armazenar estados do bot por chat (usuário)
ultima_pergunta, ultima_categoria, pontuacao, estado_adicao = {}, {}, {}, {}

# Função que carrega os flashcards armazenados no arquivo JSON
def carregar_flashcards_por_categoria():
    # Se arquivo não existe, cria um vazio
    if not os.path.exists("flashcards.json"):
        with open("flashcards.json", "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
    # Abre e carrega os dados do arquivo JSON em um dicionário
    with open("flashcards.json", "r", encoding="utf-8") as f:
        return json.load(f)

# Carrega os flashcards na inicialização
flashcards_por_categoria = carregar_flashcards_por_categoria()

# Função para recarregar flashcards ao detectar alteração no arquivo JSON
def recarregar_flashcards():
    global flashcards_por_categoria
    flashcards_por_categoria = carregar_flashcards_por_categoria()
    print("🔄 Flashcards recarregados.")

# Classe que monitora o arquivo flashcards.json para alterações usando watchdog
class FlashcardFileHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop

    # Método chamado quando arquivo é modificado
    def on_modified(self, event):
        # Se o arquivo modificado é o flashcards.json, dispara reload thread-safe
        if event.src_path.endswith("flashcards.json"):
            self.loop.call_soon_threadsafe(recarregar_flashcards)

# Inicia o observador watchdog que monitora o arquivo JSON para recarregar os flashcards automaticamente
def iniciar_watchdog(loop):
    observer = Observer()
    observer.schedule(FlashcardFileHandler(loop), path='.', recursive=False)
    observer.start()
    return observer

# Salva um flashcard novo no arquivo JSON, adicionando à categoria correta
def salvar_flashcard(card):
    dados = carregar_flashcards_por_categoria()
    dados.setdefault(card["categoria"], []).append({
        "pergunta": card["pergunta"],
        "resposta": card["resposta"]
    })
    with open("flashcards.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

# Função para limpar texto: tira acentos, pontuações, espaços extras e deixa tudo minúsculo
def limpar_texto(texto):
    texto = unicodedata.normalize('NFD', texto.lower())
    texto = re.sub(r'[^\w\s]', '', texto)  # remove caracteres não alfanuméricos
    # remove marcas de acentuação e espaços extras
    return re.sub(r'\s+', ' ',
                  ''.join(c for c in texto
                          if unicodedata.category(c) != 'Mn')).strip()

# Verifica se duas respostas são similares o suficiente usando difflib (limite padrão 85%)
def respostas_sao_semelhantes(r1, r2, limite=0.85):
    return difflib.SequenceMatcher(None, r1, r2).ratio() >= limite

# Teclado padrão com opções usadas pelo bot no Telegram
def teclado_padrao():
    return ReplyKeyboardMarkup([["Categorias", "Próxima", "Resposta"],
                                ["Acertou", "Errou"], ["Adicionar"]],
                               resize_keyboard=True)

# Comando /start que envia mensagem de boas-vindas e instruções
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = ("📚 Bot de flashcards estilo Anki.\n\n"
           "👉 Categorias — selecione uma.\n"
           "👉 Próxima — pergunta aleatória.\n"
           "👉 Resposta — veja a resposta.\n"
           "👉 Acertou / Errou — registre.\n"
           "👉 Adicionar — novo flashcard.")
    await update.message.reply_text(msg, reply_markup=teclado_padrao())

# Lista categorias disponíveis para o usuário escolher
async def listar_categorias(update, context):
    categorias = [[c] for c in flashcards_por_categoria]
    await update.message.reply_text("Escolha uma categoria:",
                                    reply_markup=ReplyKeyboardMarkup(
                                        categorias, resize_keyboard=True))

# Comando /reload para recarregar os flashcards do arquivo JSON manualmente
async def reload_command(update, context):
    recarregar_flashcards()
    await update.message.reply_text("🔄 Flashcards recarregados!",
                                    reply_markup=teclado_padrao())

# Envia a próxima pergunta, aleatória da categoria escolhida ou de todas se nenhuma selecionada
async def proxima(update, context):
    chat_id = update.effective_chat.id
    categoria = ultima_categoria.get(chat_id)
    perguntas = flashcards_por_categoria.get(categoria, [])

    if not perguntas:
        # Se não tem perguntas na categoria, pega todas
        todas = [
            p for plist in flashcards_por_categoria.values() for p in plist
        ]
        if not todas:
            await update.message.reply_text("❗ Nenhum flashcard disponível.")
            return
        pergunta = random.choice(todas)
    else:
        pergunta = random.choice(perguntas)

    # Armazena a pergunta atual para o chat
    ultima_pergunta[chat_id] = pergunta
    await update.message.reply_text(
        f"📖 {pergunta['pergunta']}\n👉 Use Resposta para ver.",
        reply_markup=teclado_padrao())

# Mostra a resposta da última pergunta para o usuário
async def responder(update, context):
    chat_id = update.effective_chat.id
    if chat_id in ultima_pergunta:
        await update.message.reply_text(
            f"✅ Resposta: {ultima_pergunta[chat_id]['resposta']}",
            reply_markup=teclado_padrao())
    else:
        await update.message.reply_text("❗ Use Próxima antes.",
                                        reply_markup=teclado_padrao())

# Marca que o usuário acertou a pergunta atual
async def acertou(update, context):
    await registrar_pontuacao(update, "acertos", "✅ Acerto registrado!")

# Marca que o usuário errou a pergunta atual
async def errou(update, context):
    await registrar_pontuacao(update, "erros", "❌ Erro registrado!")

# Função auxiliar para registrar a pontuação (acertos ou erros)
async def registrar_pontuacao(update, tipo, msg):
    chat_id = update.effective_chat.id
    pontuacao.setdefault(chat_id, {"acertos": 0, "erros": 0})
    pontuacao[chat_id][tipo] += 1
    p = pontuacao[chat_id]
    await update.message.reply_text(
        f"{msg}\nAcertos: {p['acertos']} | Erros: {p['erros']}",
        reply_markup=teclado_padrao())

# Inicia o fluxo para adicionar um novo flashcard, pedindo categoria ou criação dela
async def adicionar(update, context):
    categorias = [["➕ Nova categoria"]] + [[c]
                                           for c in flashcards_por_categoria]
    estado_adicao[update.effective_chat.id] = {"etapa": "categoria"}
    await update.message.reply_text("Escolha ou crie categoria:",
                                    reply_markup=ReplyKeyboardMarkup(
                                        categorias, resize_keyboard=True))

# Função que trata todas as mensagens de texto enviadas pelo usuário (menu principal e fluxo adicionar)
async def handler_textos(update, context):
    texto = update.message.text
    chat_id = update.effective_chat.id

    # Se estiver no processo de adicionar flashcard, chama fluxo específico
    if chat_id in estado_adicao:
        await tratar_resposta(update, context)
        return

    comandos = {
        "Categorias": listar_categorias,
        "Próxima": proxima,
        "Resposta": responder,
        "Acertou": acertou,
        "Errou": errou,
        "Adicionar": adicionar
    }
    # Se texto é um comando conhecido, executa
    if texto in comandos:
        await comandos[texto](update, context)
    # Se texto é uma categoria, seleciona ela para o chat atual
    elif texto in flashcards_por_categoria:
        ultima_categoria[chat_id] = texto
        await update.message.reply_text(f"Categoria '{texto}' selecionada.",
                                        reply_markup=teclado_padrao())
    else:
        await update.message.reply_text("Comando ou categoria inválido.",
                                        reply_markup=teclado_padrao())

# Fluxo de adicionar um flashcard novo: categoria, pergunta e resposta
async def tratar_resposta(update, context):
    chat_id = update.effective_chat.id
    texto = update.message.text
    estado = estado_adicao[chat_id]

    if estado["etapa"] == "categoria":
        if texto == "➕ Nova categoria":
            estado["etapa"] = "nova_categoria"
            await update.message.reply_text("Digite o nome da nova categoria:")
        elif texto in flashcards_por_categoria:
            estado.update({"categoria": texto, "etapa": "pergunta"})
            await update.message.reply_text(
                f"Categoria '{texto}' escolhida. Digite a pergunta:")
        else:
            await update.message.reply_text(
                "Categoria inválida. Escolha ou crie.")
    elif estado["etapa"] == "nova_categoria":
        if texto in flashcards_por_categoria:
            await update.message.reply_text("Essa categoria já existe.")
        else:
            flashcards_por_categoria[texto] = []
            estado.update({"categoria": texto, "etapa": "pergunta"})
            await update.message.reply_text(
                f"Categoria '{texto}' criada. Digite a pergunta:")
    elif estado["etapa"] == "pergunta":
        estado.update({"pergunta": texto, "etapa": "resposta"})
        await update.message.reply_text("Digite a resposta:")
    elif estado["etapa"] == "resposta":
        salvar_flashcard({
            "categoria": estado["categoria"],
            "pergunta": estado["pergunta"],
            "resposta": texto
        })
        await update.message.reply_text(
            f"✅ Flashcard adicionado! Categoria: {estado['categoria']}")
        del estado_adicao[chat_id]

# === Servidor web aiohttp para responder ping externo e manter bot ativo ===
async def start_webserver():
    app = web.Application()

    # Manipulador para rota raiz "/"
    async def handle(request):
        print(f"✅ Ping recebido de {request.remote}")  # Log no console
        return web.json_response(
            {
                "status": "online",
                "bot": "botmarcos",
                "user": "@marcosandre2011"
            },
            headers={"Cache-Control": "no-store"}  # Sem cache para sempre responder atual
        )

    app.router.add_get("/", handle)  # Adiciona rota GET para "/"
    runner = web.AppRunner(app)
    await runner.setup()
    # Inicia servidor escutando todas as interfaces na porta 3000
    await web.TCPSite(runner, '0.0.0.0', 3000).start()
    print("🌐 Servidor aiohttp rodando na porta 3000")

# Função principal que configura o bot, handlers e inicia webserver + polling Telegram
async def main_async():
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reload", reload_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handler_textos))
    await start_webserver()  # Inicia servidor aiohttp paralelo
    await app.run_polling(stop_signals=None)  # Inicia polling para receber atualizações Telegram

if __name__ == "__main__":
    # Loop asyncio principal para rodar o bot e o watchdog simultaneamente
    loop = asyncio.get_event_loop()
    observer = iniciar_watchdog(loop)  # Inicia observador para monitorar arquivo JSON
    nest_asyncio.apply()  # Permite rodar loop asyncio dentro de loop já rodando (caso REPL)
    try:
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()  # Para observador quando o programa terminar
        observer.join()
