import subprocess

try:
    with open("./archivo.txt", "r") as archivo:
        for linea in archivo:
            contenido = linea.strip()
            if contenido:
                # Comando a ejecutar
                command = [
                    "./yt-dlp",
                    "-x",
                    "--audio-format", "mp3",
                    "-o", "out/%(title)s.%(ext)s",
                    contenido
                ]
                print(f"\033[33m-> {contenido}\033[0m")
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                print("\033[32mComando ejecutado correctamente\033[0m")
                print("\033[34mSalida\033[0m")
                print(result.stdout)
except FileNotFoundError as e:
    print(f"\033[31mEl archivo no fue encontrado: {str(e)}\033[0m")
except IOError as e:
    print(f"\033[31mOcurrió un error al leer el archivo: {str(e)}\033[0m")
except subprocess.CalledProcessError as e:
    print("\033[31mError al ejecutar el comando.\033[0m")
    print("\033[31mErrores estándar:\033[0m")
    print(e.stderr)
    
print("\033[32mLectura de links completada\033[0m")
