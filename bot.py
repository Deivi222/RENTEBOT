from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import sqlite3

# ID del administrador
ADMIN_ID = 5830863181

# Token de tu bot
TOKEN = '7711960500:AAG3qR3LEoeorKVwB_y7LYKylsVjopOrr8Y'

# Inicializar la base de datos y tablas
def inicializar_base_de_datos():
    conn = sqlite3.connect('notas.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departamento_id INTEGER NOT NULL,
            contenido TEXT NOT NULL,
            FOREIGN KEY (departamento_id) REFERENCES departamentos (id)
        )
    ''')
    
    # Insertar departamentos si no existen
    departamentos = ["Excitación", "Sub de 110kv", "Equipos auxiliares"]
    cursor.execute('SELECT COUNT(*) FROM departamentos')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO departamentos (nombre) VALUES (?)', [(d,) for d in departamentos])
    
    conn.commit()
    conn.close()

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    teclado = [['📋 Notas']]
    if user_id == ADMIN_ID:
        teclado.append(['➕ Agregar notas', '🗑️ Eliminar notas'])
    reply_markup = ReplyKeyboardMarkup(teclado, resize_keyboard=True)
    await update.message.reply_text('¡Hola! ¿Qué quieres hacer?', reply_markup=reply_markup)

# Manejar mensajes
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    texto = update.message.text

    if texto == '📋 Notas':
        await seleccionar_departamento(update, context, 'buscar')
    elif texto == '➕ Agregar notas' and user_id == ADMIN_ID:
        await seleccionar_departamento(update, context, 'agregar')
    elif texto == '🗑️ Eliminar notas' and user_id == ADMIN_ID:
        await seleccionar_departamento(update, context, 'eliminar')
    elif texto in ['Excitación', 'Sub de 110kv', 'Equipos auxiliares']:
        context.user_data['departamento_seleccionado'] = texto
        modo = context.user_data.get('modo')
        if modo == 'agregar':
            await update.message.reply_text(f'✍️ Escribe la nota que deseas agregar a {texto}:')
        elif modo == 'eliminar':
            await mostrar_notas_para_eliminar(update, context)
        elif modo == 'buscar':
            await update.message.reply_text(f'🔍 Escribe una palabra clave para buscar en {texto}:')
    elif texto.startswith('❌ '):
        try:
            note_id = int(texto.split(' ')[1])  # Obtener el ID después de "❌ "
            await eliminar_nota(update, context, note_id)
        except ValueError:
            await update.message.reply_text("❌ Error al identificar la nota.")
    elif texto == '🔙 Volver':
        await start(update, context)
        context.user_data.clear()
    elif 'departamento_seleccionado' in context.user_data:
        modo = context.user_data.get('modo')
        if modo == 'agregar' and user_id == ADMIN_ID:
            await agregar_nota(update, context, texto)
        elif modo == 'buscar':
            await buscar_nota(update, context, texto)
            context.user_data.clear()

# Función para seleccionar departamento según modo
async def seleccionar_departamento(update: Update, context: ContextTypes.DEFAULT_TYPE, modo: str):
    teclado = ReplyKeyboardMarkup([
        ['Excitación', 'Sub de 110kv', 'Equipos auxiliares'],
        ['🔙 Volver']
    ], resize_keyboard=True)
    context.user_data['modo'] = modo
    await update.message.reply_text('Selecciona un departamento:', reply_markup=teclado)

# Función para agregar una nota
async def agregar_nota(update: Update, context: ContextTypes.DEFAULT_TYPE, contenido: str):
    departamento = context.user_data['departamento_seleccionado']
    conn = sqlite3.connect('notas.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM departamentos WHERE nombre = ?', (departamento,))
    res = cursor.fetchone()
    if res:
        departamento_id = res[0]
        cursor.execute('INSERT INTO notas (departamento_id, contenido) VALUES (?, ?)', (departamento_id, contenido))
        conn.commit()
        await update.message.reply_text(f"✅ Nota agregada a {departamento}.")
    conn.close()

# Función para buscar notas con división de mensajes
async def buscar_nota(update: Update, context: ContextTypes.DEFAULT_TYPE, palabra_clave: str):
    departamento = context.user_data['departamento_seleccionado']
    conn = sqlite3.connect('notas.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT contenido FROM notas
        JOIN departamentos ON notas.departamento_id = departamentos.id
        WHERE departamentos.nombre = ? AND contenido LIKE ?
    ''', (departamento, f'%{palabra_clave}%'))
    resultados = cursor.fetchall()
    conn.close()

    if resultados:
        respuesta = f"🔍 Notas encontradas en {departamento}:\n"
        mensajes = []
        mensaje_actual = respuesta

        for r in resultados:
            linea = f"- {r[0]}\n"
            if len(mensaje_actual) + len(linea) > 4000:
                mensajes.append(mensaje_actual)
                mensaje_actual = "🔍 Más notas:\n"
            mensaje_actual += linea
        
        mensajes.append(mensaje_actual)

        for mensaje in mensajes:
            await update.message.reply_text(mensaje)
    else:
        await update.message.reply_text(f"🔍 No se encontraron notas en {departamento} con '{palabra_clave}'.")

# Función para mostrar notas para eliminar con IDs
async def mostrar_notas_para_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    departamento = context.user_data['departamento_seleccionado']
    conn = sqlite3.connect('notas.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT notas.id, notas.contenido FROM notas
        JOIN departamentos ON notas.departamento_id = departamentos.id
        WHERE departamentos.nombre = ?
    ''', (departamento,))
    notas = cursor.fetchall()
    conn.close()

    if notas:
        teclado = ReplyKeyboardMarkup(
            [[f"❌ {nota[0]} - {nota[1][:30]}..."] for nota in notas] + [['🔙 Volver']],
            resize_keyboard=True
        )
        await update.message.reply_text(f"Notas en {departamento}:\nSelecciona una para eliminar:", reply_markup=teclado)
    else:
        await update.message.reply_text(f"❌ No hay notas en {departamento}.")

# Función para eliminar una nota por ID
async def eliminar_nota(update: Update, context: ContextTypes.DEFAULT_TYPE, note_id: int):
    conn = sqlite3.connect('notas.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notas WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Nota eliminada.")
    await mostrar_notas_para_eliminar(update, context)

def main():
    inicializar_base_de_datos()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    application.run_polling()

if __name__ == '__main__':
    main()
