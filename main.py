import os
import sys
import time
import signal
import threading
import concurrent.futures
import yt_dlp
import questionary
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.text import Text
from rich.console import Console

# Global configuration and state
stop_event = threading.Event()
console = Console()

# Use raw strings for ASCII art
JESDEV_ART = r"""[bold cyan]
     ██╗███████╗███████╗██████╗ ███████╗██╗   ██╗ ██╗██████╗ ██╗   ██╗
     ██║██╔════╝██╔════╝██╔══██╗██╔════╝██║   ██║███║╚════██╗██║   ██║
     ██║█████╗  ███████╗██║  ██║█████╗  ██║   ██║╚██║ █████╔╝██║   ██║
██   ██║██╔══╝  ╚════██║██║  ██║██╔══╝  ╚██╗ ██╔╝ ██║██╔═══╝ ██║   ██║
╚█████╔╝███████╗███████║██████╔╝███████╗ ╚████╔╝  ██║███████╗╚██████╔╝
 ╚════╝ ╚══════╝╚══════╝╚═════╝ ╚══════╝  ╚═══╝   ╚═╝╚══════╝ ╚═════╝ 
[/bold cyan]"""

# YouTube brand red is roughly #FF0000
YOUTUBE_DOWNLOADER_ART = r"""[bold red]
  ▄▄▄                                          ▄▄▄▄▄▄                       ▄▄                               
 █▀██  ██              █▄       █▄            █▀██▀▀██                       ██                █▄            
   ██  ██             ▄██▄      ██              ██   ██                ▄     ██                ██       ▄    
   ██  ██  ▄███▄ ██ ██ ██ ██ ██ ████▄ ▄█▀█▄     ██   ██ ▄███▄▀█▄ █▄ ██▀████▄ ██ ▄███▄ ▄▀▀█▄ ▄████ ▄█▀█▄ ████▄
   ██  ██  ██ ██ ██ ██ ██ ██ ██ ██ ██ ██▄█▀   ▄ ██   ██ ██ ██ ██▄██▄██ ██ ██ ██ ██ ██ ▄█▀██ ██ ██ ██▄█▀ ██   
   ▀█████▄▄▀███▀▄▀██▀█▄██▄▀██▀█▄████▀▄▀█▄▄▄   ▀██▀███▀ ▄▀███▀  ▀██▀██▀▄██ ▀█▄██▄▀███▀▄▀█▄██▄█▀███▄▀█▄▄▄▄█▀   
   ▄   ██                                                                                                    
   ▀████▀
[/bold red]"""

class MyLogger:
    """Silences yt-dlp stdout/stderr output."""
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

class SmartDownloadColumn(DownloadColumn):
    def render(self, task):
        if "Progreso Total" in task.description:
            return Text("")
        return super().render(task)

class SmartSpeedColumn(TransferSpeedColumn):
    def render(self, task):
        if "Progreso Total" in task.description:
            speed = task.speed
            if speed is None: return Text("")
            if speed < 0.1:
                return Text(f"{speed * 60:.1f} arch/min", style="dim cyan")
            return Text(f"{speed:.2f} arch/s", style="dim cyan")
        return super().render(task)

def handle_sigint(signum, frame):
    if not stop_event.is_set():
        stop_event.set()
        console.print("\n[dim yellow]Deteniendo...[/dim yellow]")
    else:
        sys.exit(1)

signal.signal(signal.SIGINT, handle_sigint)

def download_video(url, progress, format_type, global_task_id):
    if stop_event.is_set():
        return

    task_id = progress.add_task("", status="...", total=None, visible=False)
    progress.update(task_id, visible=True, description=f"{url[:15]}...", status="Iniciando")

    def progress_hook(d):
        if stop_event.is_set():
            raise Exception("Stop")

        if d['status'] == 'downloading':
            if 'info_dict' in d and d['info_dict'].get('title'):
                title = d['info_dict']['title']
                display_name = (title[:20] + "..") if len(title) > 20 else title.ljust(22)
                progress.update(task_id, description=f"[blue]{display_name}[/blue]", status="Bajando")

            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            
            if total:
                progress.update(task_id, total=total, completed=downloaded)
                
        elif d['status'] == 'finished':
            progress.update(task_id, status="Procesando")

    ydl_opts = {
        'outtmpl': 'out/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'logger': MyLogger(), 
        'progress_hooks': [progress_hook],
        'writethumbnail': True,
        'noprogress': True,
    }

    if format_type == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [
                {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'},
                {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegMetadata'},
            ],
        })
    else:
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'postprocessors': [
                {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegMetadata'},
            ],
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if stop_event.is_set(): return
            ydl.download([url])
            
            progress.update(task_id, status="[dim green]Listo[/dim green]", total=1, completed=1)
            progress.advance(global_task_id)
            time.sleep(1)
            progress.remove_task(task_id)
            
    except Exception as e:
        err_msg = str(e)
        short_err = "Error"
        
        if "Private video" in err_msg:
            short_err = "Privado"
        elif "Video unavailable" in err_msg:
            short_err = "No disponible"
        elif "copyright" in err_msg.lower():
            short_err = "Copyright"
        elif "account" in err_msg.lower() and "closed" in err_msg.lower():
            short_err = "Cuenta cerrada"
        elif "Incomplete" in err_msg:
             short_err = "Incompleto"
        
        try:
            with open("errors.log", "a") as log:
                log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {url} -> {err_msg}\n")
        except:
            pass

        if not stop_event.is_set():
            progress.update(task_id, status=f"[dim red]{short_err}[/dim red]")
            progress.advance(global_task_id) 
            time.sleep(2)
            progress.remove_task(task_id)

def main():
    if not os.path.exists('out'):
        os.makedirs('out')

    console.print(JESDEV_ART)
    console.print(YOUTUBE_DOWNLOADER_ART)

    try:
        format_type = questionary.select(
            "Selecciona formato:",
            choices=[
                questionary.Choice("Audio (MP3)", value="mp3"),
                questionary.Choice("Video (MP4)", value="mp4"),
            ],
            style=questionary.Style([
                ('qmark', 'fg:#5f819d bold'),
                ('question', 'bold fg:#5f819d'),
                ('answer', 'fg:#5f819d bold'),
                ('pointer', 'fg:#5f819d bold'),
                ('highlighted', 'fg:#5f819d bold'),
                ('selected', 'fg:#5f819d'),
                ('separator', 'fg:#cc5454'),
                ('instruction', ''),
                ('text', ''),
                ('disabled', 'fg:#858585 italic')
            ])
        ).ask()
    except KeyboardInterrupt:
        return

    if not format_type: return

    try:
        with open("links", "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        console.print("[dim red]No existe 'links'[/dim red]")
        return

    if not urls:
        console.print("[dim yellow]'links' vacío[/dim yellow]")
        return

    progress = Progress(
        TextColumn("{task.description}"),
        TextColumn("[dim white]{task.fields[status]}"),
        BarColumn(
            bar_width=20, 
            style="dim white", 
            complete_style="blue", 
            finished_style="green"
        ), 
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), # Added percentage
        SmartDownloadColumn(),
        SmartSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True
    )

    global_task_id = progress.add_task(
        "[bold cyan]Progreso Total[/bold cyan]", 
        total=len(urls), 
        status=f"0/{len(urls)}"
    )

    with progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(download_video, url, progress, format_type, global_task_id) for url in urls]
            
            while any(not f.done() for f in futures):
                completed = progress.tasks[global_task_id].completed
                total = progress.tasks[global_task_id].total
                progress.update(global_task_id, status=f"[bold white]{int(completed)}/{int(total)}[/bold white]")
                if stop_event.wait(timeout=0.2):
                    break
            
            completed = progress.tasks[global_task_id].completed
            total = progress.tasks[global_task_id].total
            progress.update(global_task_id, status=f"[bold green]{int(completed)}/{int(total)}[/bold green]")

    if stop_event.is_set():
        console.print("\n[dim yellow]Cancelado[/dim yellow]")
    else:
        if os.path.exists("errors.log") and os.path.getsize("errors.log") > 0:
            console.print("\n[bold blue]¡Finalizado![/bold blue] [dim](Revisa errors.log para ver fallos)[/dim]")
        else:
            console.print("\n[bold blue]¡Finalizado![/bold blue]")

if __name__ == "__main__":
    main()
