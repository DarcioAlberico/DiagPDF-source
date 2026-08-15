"""Interface and document strings in the four supported languages.

One dictionary per key, one entry per language. The previous shape — 3-tuples
for en/ru/pt plus a separate T_ES dict and a separate LAYOUTS_ES tuple — meant
Spanish was reached through an index overflow, and a key added to one catalogue
could silently miss the others.
"""

from __future__ import annotations

from typing import Any

from .layouts import LAYOUTS

LANGS: tuple[str, ...] = ('en', 'ru', 'pt', 'es')
DEFAULT_LANG = 'en'

# What each code is called, in its own language and in English. Kept next to
# LANGS so that adding a language there and forgetting it here is caught by a
# test rather than printed as a bare code.
LANG_NAMES: dict[str, tuple[str, str]] = {
    'en': ('English', 'English'),
    'ru': ('Русский', 'Russian'),
    'pt': ('Português', 'Portuguese'),
    'es': ('Español', 'Spanish'),
}


def lang_label(lang: str) -> str:
    """Return a human-readable name for a language code."""
    endonym, english = LANG_NAMES.get(lang, (lang, lang))
    return endonym if endonym == english else f'{endonym} ({english})'

T: dict[str, dict[str, Any]] = {
    'section_files': {
        'en': 'Files',
        'ru': 'Файлы',
        'pt': 'Arquivos',
        'es': 'Archivos',
    },
    'section_page': {
        'en': 'Page',
        'ru': 'Страница',
        'pt': 'Página',
        'es': 'Página',
    },
    'section_diagram': {
        'en': 'Diagram',
        'ru': 'Диаграмма',
        'pt': 'Diagrama',
        'es': 'Diagrama',
    },
    'input_file': {
        'en': 'Input file:',
        'ru': 'Исходный файл:',
        'pt': 'Arquivo de entrada:',
        'es': 'Archivo de entrada:',
    },
    'output_pdf': {
        'en': 'Output file:',
        'ru': 'Выходной файл:',
        'pt': 'Arquivo de saída:',
        'es': 'Archivo de salida:',
    },
    'header_text': {
        'en': 'Header:',
        'ru': 'Верхний:',
        'pt': 'Cabeçalho:',
        'es': 'Encabezado:',
    },
    'footer_text': {
        'en': 'Footer:',
        'ru': 'Нижний:',
        'pt': 'Rodapé:',
        'es': 'Pie de página:',
    },
    'show_header': {
        'en': 'Show',
        'ru': 'Показать',
        'pt': 'Mostrar',
        'es': 'Mostrar',
    },
    'show_footer': {
        'en': 'Show',
        'ru': 'Показать',
        'pt': 'Mostrar',
        'es': 'Mostrar',
    },
    'layout': {
        'en': 'Layout:',
        'ru': 'Макет:',
        'pt': 'Layout:',
        'es': 'Diseño:',
    },
    'font': {
        'en': 'Font:',
        'ru': 'Шрифт:',
        'pt': 'Fonte:',
        'es': 'Fuente:',
    },
    'symbol': {
        'en': 'Move indicator:',
        'ru': 'Символ хода:',
        'pt': 'Indicador de lado:',
        'es': 'Indicador de turno:',
    },
    'lines_count': {
        'en': 'Lines per diagram:',
        'ru': 'Строк под диаграммой:',
        'pt': 'Linhas por diagrama:',
        'es': 'Líneas por diagrama:',
    },
    'lines_plain': {
        'en': 'Plain',
        'ru': 'Пустые',
        'pt': 'Simples',
        'es': 'Simples',
    },
    'lines_numbered': {
        'en': 'Numbered',
        'ru': 'С нумерацией',
        'pt': 'Numeradas',
        'es': 'Numeradas',
    },
    'orient': {
        'en': 'Orientation:',
        'ru': 'Ориентация:',
        'pt': 'Orientação:',
        'es': 'Orientación:',
    },
    'orient_auto': {
        'en': 'Auto',
        'ru': 'Авто',
        'pt': 'Automático',
        'es': 'Automático',
    },
    'orient_white': {
        'en': 'White ↓',
        'ru': 'Белые ↓',
        'pt': 'Brancas ↓',
        'es': 'Blancas ↓',
    },
    'orient_black': {
        'en': 'Black ↓',
        'ru': 'Чёрные ↓',
        'pt': 'Pretas ↓',
        'es': 'Negras ↓',
    },
    'border_style': {
        'en': 'Border:',
        'ru': 'Рамка:',
        'pt': 'Borda:',
        'es': 'Borde:',
    },
    'border_simple': {
        'en': 'Simple',
        'ru': 'Одинарная',
        'pt': 'Simples',
        'es': 'Simple',
    },
    'border_double': {
        'en': 'Double',
        'ru': 'Двойная',
        'pt': 'Dupla',
        'es': 'Doble',
    },
    'border_none': {
        'en': 'None',
        'ru': 'Без рамки',
        'pt': 'Sem borda',
        'es': 'Sin borde',
    },
    'coords': {
        'en': 'Show coordinates',
        'ru': 'Показать координаты',
        'pt': 'Mostrar coordenadas',
        'es': 'Mostrar coordenadas',
    },
    'title_source': {
        'en': 'Title template:',
        'ru': 'Шаблон заголовка:',
        'pt': 'Modelo do título:',
        'es': 'Plantilla del título:',
    },
    'tpl_help_title': {
        'en': 'Title template variables',
        'ru': 'Переменные шаблона заголовка',
        'pt': 'Variáveis do modelo do título',
        'es': 'Variables de la plantilla del título',
    },
    'tpl_help_body': {
        'en': (
            '{number}  — diagram number          e.g.  42\n'
            '{event}   — [Event "…"] tag         e.g.  Hastings 1895\n'
            '{white}   — [White "…"] tag         e.g.  Steinitz, W.\n'
            '{black}   — [Black "…"] tag         e.g.  Lasker, Em.\n'
            '{date}    — [Date "…"] tag          e.g.  1895.01.03\n'
            '{comment} — first comment in game   e.g.  White to move and win\n'
            '\n'
            'Example:  {number}. {event} ({date})\n'
            '→  42. Hastings 1895 (1895.01.03)'
        ),
        'ru': (
            '{number}  — номер диаграммы         напр.  42\n'
            '{event}   — тег [Event "…"]         напр.  Гастингс 1895\n'
            '{white}   — тег [White "…"]         напр.  Steinitz, W.\n'
            '{black}   — тег [Black "…"]         напр.  Lasker, Em.\n'
            '{date}    — тег [Date "…"]          напр.  1895.01.03\n'
            '{comment} — первый коммент. партии  напр.  Белые ходят и выигрывают\n'
            '\n'
            'Пример:  {number}. {event} ({date})\n'
            '→  42. Гастингс 1895 (1895.01.03)'
        ),
        'pt': (
            '{number}  — número do diagrama      ex.   42\n'
            '{event}   — tag [Event "…"]         ex.   Hastings 1895\n'
            '{white}   — tag [White "…"]         ex.   Steinitz, W.\n'
            '{black}   — tag [Black "…"]         ex.   Lasker, Em.\n'
            '{date}    — tag [Date "…"]          ex.   1895.01.03\n'
            '{comment} — primeiro comentário     ex.   Brancas jogam e ganham\n'
            '\n'
            'Exemplo:  {number}. {event} ({date})\n'
            '→  42. Hastings 1895 (1895.01.03)'
        ),
        'es': (
            '{number}  — número del diagrama     ej.   42\n'
            '{event}   — etiqueta [Event "…"]    ej.   Hastings 1895\n'
            '{white}   — etiqueta [White "…"]    ej.   Steinitz, W.\n'
            '{black}   — etiqueta [Black "…"]    ej.   Lasker, Em.\n'
            '{date}    — etiqueta [Date "…"]     ej.   1895.01.03\n'
            '{comment} — primer comentario       ej.   Juegan blancas y ganan\n'
            '\n'
            'Ejemplo:  {number}. {event} ({date})\n'
            '→  42. Hastings 1895 (1895.01.03)'
        ),
    },
    'sym_square': {
        'en': 'Square',
        'ru': 'Квадрат',
        'pt': 'Quadrado',
        'es': 'Cuadrado',
    },
    'sym_circle': {
        'en': 'Circle',
        'ru': 'Круг',
        'pt': 'Círculo',
        'es': 'Círculo',
    },
    'sym_triangle': {
        'en': 'Triangle',
        'ru': 'Треугольник',
        'pt': 'Triângulo',
        'es': 'Triángulo',
    },
    'font_size_lbl': {
        'en': 'Board font size (0=auto)',
        'ru': 'Размер шрифта доски (0=авто)',
        'pt': 'Tamanho da fonte do tabuleiro (0=auto)',
        'es': 'Tamaño de fuente del tablero (0=auto)',
    },
    'lichess_link': {
        'en': 'Lichess links',
        'ru': 'Ссылки Lichess',
        'pt': 'Links do Lichess',
        'es': 'Enlaces de Lichess',
    },
    'answers_section': {
        'en': 'Add answers section',
        'ru': 'Добавить раздел ответов',
        'pt': 'Adicionar seção de respostas',
        'es': 'Añadir sección de respuestas',
    },
    'answers_title_lbl': {
        'en': 'Answers heading',
        'ru': 'Заголовок раздела ответов',
        'pt': 'Título das respostas',
        'es': 'Título de respuestas',
    },
    'answers_cols_lbl': {
        'en': 'Answer columns',
        'ru': 'Колонок ответов',
        'pt': 'Colunas de respostas',
        'es': 'Columnas de respuestas',
    },
    'figurine_font_lbl': {
        'en': 'Figurine font',
        'ru': 'Шрифт фигур',
        'pt': 'Fonte figurativa',
        'es': 'Fuente figurativa',
    },
    'convert': {
        'en': 'Generate File',
        'ru': 'Сгенерировать файл',
        'pt': 'Gerar Arquivo',
        'es': 'Generar archivo',
    },
    'open_pdf': {
        'en': 'Open file',
        'ru': 'Открыть файл',
        'pt': 'Abrir arquivo',
        'es': 'Abrir archivo',
    },
    'open_title': {
        'en': 'Open chess file',
        'ru': 'Открыть шахматный файл',
        'pt': 'Abrir arquivo de xadrez',
        'es': 'Abrir archivo de ajedrez',
    },
    'save_title': {
        'en': 'Save file as',
        'ru': 'Сохранить файл как',
        'pt': 'Salvar como',
        'es': 'Guardar archivo como',
    },
    'css_open_title': {
        'en': 'Import CSS file',
        'ru': 'Импорт CSS-файла',
        'pt': 'Importar arquivo CSS',
        'es': 'Importar archivo CSS',
    },
    'css_prompt_title': {
        'en': 'EPUB CSS',
        'ru': 'CSS для EPUB',
        'pt': 'CSS do EPUB',
        'es': 'CSS del EPUB',
    },
    'css_prompt_body': {
        'en': 'Import an extra .css file into this EPUB?',
        'ru': 'Импортировать дополнительный .css файл в этот EPUB?',
        'pt': 'Importar um arquivo .css extra para este EPUB?',
        'es': '¿Importar un archivo .css extra para este EPUB?',
    },
    'open_types': {
        'en': [('Chess files', '*.pgn *.fen *.epd'), ('All files', '*.*')],
        'ru': [('Шахматные файлы', '*.pgn *.fen *.epd'), ('Все файлы', '*.*')],
        'pt': [('Arquivos de xadrez', '*.pgn *.fen *.epd'), ('Todos os arquivos', '*.*')],
        'es': [('Archivos de ajedrez', '*.pgn *.fen *.epd'), ('Todos los archivos', '*.*')],
    },
    'save_types': {
        'en': [('PDF files', '*.pdf'), ('HTML files', '*.html'), ('EPUB files', '*.epub'), ('DOCX files', '*.docx'), ('RTF files', '*.rtf'), ('All files', '*.*')],
        'ru': [('PDF файлы', '*.pdf'), ('HTML файлы', '*.html'), ('EPUB файлы', '*.epub'), ('DOCX файлы', '*.docx'), ('RTF файлы', '*.rtf'), ('Все файлы', '*.*')],
        'pt': [('Arquivos PDF', '*.pdf'), ('Arquivos HTML', '*.html'), ('Arquivos EPUB', '*.epub'), ('Arquivos DOCX', '*.docx'), ('Arquivos RTF', '*.rtf'), ('Todos os arquivos', '*.*')],
        'es': [('Archivos PDF', '*.pdf'), ('Archivos HTML', '*.html'), ('Archivos EPUB', '*.epub'), ('Archivos DOCX', '*.docx'), ('Archivos RTF', '*.rtf'), ('Todos los archivos', '*.*')],
    },
    'pos_from_lbl': {
        'en': 'Positions',
        'ru': 'Позиции',
        'pt': 'Posições',
        'es': 'Posiciones',
    },
    'pos_to_lbl': {
        'en': 'to',
        'ru': 'по',
        'pt': 'até',
        'es': 'a',
    },
    'renumber_lbl': {
        'en': 'Start numbers from 1',
        'ru': 'Нумерация с 1',
        'pt': 'Iniciar numeração em 1',
        'es': 'Iniciar numeración desde 1',
    },
    'err_range': {
        'en': 'No positions in selected range.',
        'ru': 'Нет позиций в выбранном диапазоне.',
        'pt': 'Nenhuma posição no intervalo selecionado.',
        'es': 'No hay posiciones en el rango seleccionado.',
    },
    'err_not_found': {
        'en': (
            'Input file not found:\n'
            '{}'
        ),
        'ru': (
            'Файл не найден:\n'
            '{}'
        ),
        'pt': (
            'Arquivo de entrada não encontrado:\n'
            '{}'
        ),
        'es': (
            'Archivo de entrada no encontrado:\n'
            '{}'
        ),
    },
    'err_unknown': {
        'en': 'Unknown file type: {}',
        'ru': 'Неизвестный тип файла: {}',
        'pt': 'Tipo de arquivo desconhecido: {}',
        'es': 'Tipo de archivo desconocido: {}',
    },
    'err_no_pos': {
        'en': 'No positions found in file.',
        'ru': 'В файле не найдено позиций.',
        'pt': 'Nenhuma posição encontrada no arquivo.',
        'es': 'No se encontraron posiciones en el archivo.',
    },
    'done': {
        'en': 'Done: {} position(s) → {}',
        'ru': 'Готово: {} позиц. → {}',
        'pt': 'Concluído: {} posição(ões) → {}',
        'es': 'Listo: {} posición(es) → {}',
    },
    'error': {
        'en': 'Error: {}',
        'ru': 'Ошибка: {}',
        'pt': 'Erro: {}',
        'es': 'Error: {}',
    },
    'ready': {
        'en': 'Ready.',
        'ru': 'Готово.',
        'pt': 'Pronto.',
        'es': 'Listo.',
    },
    'profile_lbl': {
        'en': 'Profile:',
        'ru': 'Профиль:',
        'pt': 'Perfil:',
        'es': 'Perfil:',
    },
    'profile_load': {
        'en': 'Load',
        'ru': 'Загрузить',
        'pt': 'Carregar',
        'es': 'Cargar',
    },
    'profile_save': {
        'en': 'Save as...',
        'ru': 'Сохранить как...',
        'pt': 'Salvar como...',
        'es': 'Guardar como...',
    },
    'profile_delete': {
        'en': 'Delete',
        'ru': 'Удалить',
        'pt': 'Excluir',
        'es': 'Eliminar',
    },
    'profile_name': {
        'en': 'Name for this profile:',
        'ru': 'Название профиля:',
        'pt': 'Nome deste perfil:',
        'es': 'Nombre de este perfil:',
    },
    'profile_saved': {
        'en': 'Profile "{}" saved.',
        'ru': 'Профиль «{}» сохранён.',
        'pt': 'Perfil "{}" salvo.',
        'es': 'Perfil "{}" guardado.',
    },
    'profile_loaded': {
        'en': 'Profile "{}" loaded.',
        'ru': 'Профиль «{}» загружен.',
        'pt': 'Perfil "{}" carregado.',
        'es': 'Perfil "{}" cargado.',
    },
    'profile_deleted': {
        'en': 'Profile "{}" deleted.',
        'ru': 'Профиль «{}» удалён.',
        'pt': 'Perfil "{}" excluído.',
        'es': 'Perfil "{}" eliminado.',
    },
    'profile_none': {
        'en': 'Pick a profile first.',
        'ru': 'Сначала выберите профиль.',
        'pt': 'Escolha um perfil primeiro.',
        'es': 'Elija un perfil primero.',
    },
    'lang_btn': {
        'en': 'RU',
        'ru': 'PT',
        'pt': 'EN',
        'es': 'EN',
    },
    'lichess_analyse': {
        'en': 'Analyse on Lichess',
        'ru': 'Анализ на Lichess',
        'pt': 'Analisar no Lichess',
        'es': 'Analizar en Lichess',
    },
    'watermark_lbl': {
        'en': 'Watermark:',
        'ru': 'Водяной знак:',
        'pt': "Marca d'água:",
        'es': 'Marca de agua:',
    },
    'answers_new_page': {
        'en': 'New page',
        'ru': 'С новой страницы',
        'pt': 'Em página nova',
        'es': 'En página nueva',
    },
    'answers_after_chapter': {
        'en': 'After each chapter',
        'ru': 'После каждой главы',
        'pt': 'Após cada capítulo',
        'es': 'Tras cada capítulo',
    },
    'answers_upside_down': {
        'en': 'Upside down',
        'ru': 'Вверх ногами',
        'pt': 'De cabeça para baixo',
        'es': 'Boca abajo',
    },
    'white_to_move': {
        'en': 'White to move',
        'ru': 'Ход белых',
        'pt': 'Brancas jogam',
        'es': 'Juegan blancas',
    },
    'black_to_move': {
        'en': 'Black to move',
        'ru': 'Ход чёрных',
        'pt': 'Pretas jogam',
        'es': 'Juegan negras',
    },
    'filetype_pdf': {
        'en': 'PDF files',
        'ru': 'PDF файлы',
        'pt': 'Arquivos PDF',
        'es': 'Archivos PDF',
    },
    'filetype_html': {
        'en': 'HTML files',
        'ru': 'HTML файлы',
        'pt': 'Arquivos HTML',
        'es': 'Archivos HTML',
    },
    'filetype_epub': {
        'en': 'EPUB files',
        'ru': 'EPUB файлы',
        'pt': 'Arquivos EPUB',
        'es': 'Archivos EPUB',
    },
    'filetype_docx': {
        'en': 'DOCX files',
        'ru': 'DOCX файлы',
        'pt': 'Arquivos DOCX',
        'es': 'Archivos DOCX',
    },
    'filetype_rtf': {
        'en': 'RTF files',
        'ru': 'RTF файлы',
        'pt': 'Arquivos RTF',
        'es': 'Archivos RTF',
    },
    'filetype_md': {
        'en': 'Markdown files',
        'ru': 'Markdown файлы',
        'pt': 'Arquivos Markdown',
        'es': 'Archivos Markdown',
    },
    'filetype_tex': {
        'en': 'LaTeX files',
        'ru': 'LaTeX файлы',
        'pt': 'Arquivos LaTeX',
        'es': 'Archivos LaTeX',
    },
    'filetype_all': {
        'en': 'All files',
        'ru': 'Все файлы',
        'pt': 'Todos os arquivos',
        'es': 'Todos los archivos',
    },
    'filetype_chess': {
        'en': 'Chess files',
        'ru': 'Шахматные файлы',
        'pt': 'Arquivos de xadrez',
        'es': 'Archivos de ajedrez',
    },
    'preview': {
        'en': 'Preview',
        'ru': 'Предпросмотр',
        'pt': 'Pré-visualização',
        'es': 'Vista previa',
    },
    'preview_error': {
        'en': 'Preview unavailable',
        'ru': 'Предпросмотр недоступен',
        'pt': 'Pré-visualização indisponível',
        'es': 'Vista previa no disponible',
    },
    'cancel': {
        'en': 'Cancel',
        'ru': 'Отмена',
        'pt': 'Cancelar',
        'es': 'Cancelar',
    },
    'cancelled': {
        'en': 'Cancelled.',
        'ru': 'Отменено.',
        'pt': 'Cancelado.',
        'es': 'Cancelado.',
    },
    'working': {
        'en': 'Generating…',
        'ru': 'Создание…',
        'pt': 'Gerando…',
        'es': 'Generando…',
    },
    'epub_css_lbl': {
        'en': 'EPUB stylesheet',
        'ru': 'CSS для EPUB',
        'pt': 'Folha de estilo EPUB',
        'es': 'Hoja de estilo EPUB',
    },
    'epub_css_clear': {
        'en': 'Clear',
        'ru': 'Очистить',
        'pt': 'Limpar',
        'es': 'Borrar',
    },
    'theme': {
        'en': 'Dark theme',
        'ru': 'Тёмная тема',
        'pt': 'Tema escuro',
        'es': 'Tema oscuro',
    },
    'recent_files': {
        'en': 'Recent',
        'ru': 'Недавние',
        'pt': 'Recentes',
        'es': 'Recientes',
    },
    'credits_by': {
        'en': 'Created by ',
        'ru': 'Создано ',
        'pt': 'Criado por ',
        'es': 'Creado por ',
    },
    'credits_mod': {
        'en': ' · modified by ',
        'ru': ' · изменено ',
        'pt': ' · modificado por ',
        'es': ' · modificado por ',
    },
    'err_range_value': {
        'en': 'Positions must be whole numbers.',
        'ru': 'Позиции должны быть целыми числами.',
        'pt': 'As posições devem ser números inteiros.',
        'es': 'Las posiciones deben ser números enteros.',
    },
    'drop_hint': {
        'en': 'Drop a PGN file here',
        'ru': 'Перетащите файл PGN сюда',
        'pt': 'Solte um arquivo PGN aqui',
        'es': 'Suelta un archivo PGN aquí',
    },
    'contents': {
        'en': 'Contents',
        'ru': 'Содержание',
        'pt': 'Sumário',
        'es': 'Índice',
    },
    'page_size_lbl': {
        'en': 'Paper',
        'ru': 'Бумага',
        'pt': 'Papel',
        'es': 'Papel',
    },
    'landscape': {
        'en': 'Landscape',
        'ru': 'Альбомная',
        'pt': 'Paisagem',
        'es': 'Horizontal',
    },
    'cover': {
        'en': 'Cover page',
        'ru': 'Титульный лист',
        'pt': 'Página de rosto',
        'es': 'Portada',
    },
    'contents_lbl': {
        'en': 'Table of contents',
        'ru': 'Содержание',
        'pt': 'Sumário',
        'es': 'Índice',
    },
    'author_lbl': {
        'en': 'Author',
        'ru': 'Автор',
        'pt': 'Autor',
        'es': 'Autor',
    },
    'answers_default': {
        'en': 'Solutions',
        'ru': 'Решения',
        'pt': 'Soluções',
        'es': 'Soluciones',
    },
}


def _lang_index(lang: str) -> int:
    """Return the position of *lang* in LANGS, defaulting to English."""
    try:
        return LANGS.index(lang)
    except ValueError:
        return 0


def tr(key: str, lang: str = DEFAULT_LANG) -> Any:
    """Return the translation of *key*, falling back to English.

    Usable outside the GUI: the renderers need translated labels too.
    """
    entry = T.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry[DEFAULT_LANG])


def missing_translations() -> dict[str, list[str]]:
    """Return the languages each key is missing, for the catalogue test."""
    return {
        key: [lang for lang in LANGS if lang not in entry]
        for key, entry in T.items()
        if any(lang not in entry for lang in LANGS)
    }


def _answers_heading(opts) -> str:
    """Return the heading of the answers section, never blank.

    Takes the options duck-typed rather than imported: diagpdf.options reads its
    language list from here, so importing it back would close a cycle.
    """
    return opts.answers_title.strip() or tr('answers_default', opts.lang)


def _lichess_label(opts) -> str:
    """Return the label shown on the Lichess analysis link."""
    return opts.lichess_label.strip() or tr('lichess_analyse', opts.lang)


def _next_lang(lang: str) -> str:
    """Cycle the interface language EN -> RU -> PT -> ES -> EN."""
    return LANGS[(_lang_index(lang) + 1) % len(LANGS)]


def _layout_label(layout_idx: int, lang: str) -> str:
    """Return the localized label for a layout preset."""
    return LAYOUTS[layout_idx].label(lang)
