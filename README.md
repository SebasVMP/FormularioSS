# Formulario de contacto

Este proyecto es una página web para recibir los datos de una persona interesada en el servicio social y, si lo desea, guardar su CV. El diseño usa azul marino y dorado, e incluye los logotipos colocados en `static/images/`.

## ¿Está hecho con Flask?

La parte que recibe y procesa los formularios está hecha con **Flask**, usando Python. La página que ve la persona está escrita con **HTML y CSS**, y Flask la presenta con plantillas Jinja. Los datos se guardan en **SQLite** y los CV se conservan como archivos PDF en el servidor.

En pocas palabras: Flask conecta la página con la base de datos y el almacenamiento de archivos; no reemplaza a esas piezas.

## ¿Qué pasa cuando alguien envía el formulario?

1. La persona escribe su nombre, correo, teléfono opcional, elige una carrera y puede adjuntar un CV.
2. Flask revisa los campos y, si se adjunta un archivo, valida que tenga extensión PDF, que comience como un PDF y que no exceda 5 MB.
3. La información del formulario se guarda en la tabla `submissions`.
4. El PDF, si lo hay, se guarda por separado con un nombre generado por la aplicación. La base registra su ruta relativa y su nombre original.
5. La página muestra un folio de confirmación.

## ¿Dónde se guardan los datos?

De forma predeterminada, la aplicación crea estas rutas en la carpeta del proyecto:

- `instance/formulario.db`: base de datos SQLite.
- `instance/uploads/`: archivos PDF adjuntos.

En la base, las columnas `cv_path` y `cv_original_name` permiten relacionar cada envío con su CV. El contenido del PDF no se guarda dentro de SQLite. Por eso, para respaldar los envíos hay que conservar **la base de datos y la carpeta de archivos**.

La base se puede abrir con una herramienta como DB Browser for SQLite. Para ver los envíos que tienen CV, se puede ejecutar:

```sql
SELECT id, full_name, email, area, cv_original_name, cv_path, created_at
FROM submissions
WHERE cv_path IS NOT NULL
ORDER BY id DESC;
```

La ruta del PDF es relativa a `instance/`. Por ejemplo, si `cv_path` muestra `uploads\abc123.pdf`, el archivo está en `instance/uploads/abc123.pdf`.

## Antes de usarla con personas reales

Esta versión guarda todo en el disco donde se ejecuta la aplicación. **Todavía no está conectada a AWS ni incluye una pantalla privada para que un administrador revise o descargue los CV.** La carpeta de archivos tampoco se publica como parte de la página, pero quien tenga acceso al servidor podrá leerla.

Si se instala en un servicio de alojamiento, hay que confirmar que el disco sea persistente. Algunos servicios borran los archivos locales al reiniciar o volver a desplegar la aplicación. En ese caso se necesitaría almacenamiento persistente o integrar un servicio como Amazon S3. Como los CV contienen información personal, limita quién puede acceder al servidor y haz respaldos protegidos.

La columna antigua `message` se mantiene en la base por compatibilidad con los registros anteriores; ya no aparece en el formulario. La aplicación agrega automáticamente las columnas nuevas de los CV cuando abre una base existente y conserva sus registros.

## Requisitos

- Python 3.10 o posterior.
- Flask, que se instala desde `requirements.txt`.

## Instalación y ejecución en Windows

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Luego abre `http://127.0.0.1:8000` en el navegador. El servidor de desarrollo de Flask está pensado para pruebas locales, no para publicar una aplicación de producción tal cual.

Si se quiere guardar la base en otra ubicación, define `DATABASE_PATH` antes de iniciar la aplicación:

```powershell
$env:DATABASE_PATH = "C:\ruta\segura\formulario.db"
python app.py
```

## Carpetas principales

```text
formularioSS/
├── app.py                  # Rutas, validación y almacenamiento
├── templates/
│   └── index.html          # Formulario y estilos
├── static/
│   └── images/             # Logotipos e imágenes de la página
├── tests/
│   └── test_app.py         # Pruebas automáticas
└── instance/               # Base y CV locales (se crean al ejecutar)
```

## Ejecutar las pruebas

```powershell
python -m unittest discover -s tests -v
```
