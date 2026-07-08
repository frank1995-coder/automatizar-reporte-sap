import flet as ft
import threading
import os
import asyncio
import tkinter as tk
from tkinter import filedialog
from application.report_service import ReportService
from infrastructure.hana_repository import HanaRepository


class ProgressReporter:
    """Objeto compartido para comunicar progreso entre hilos."""
    def __init__(self):
        self.mensaje = ""
        self.fraccion = 0.0
        self.completado = False
        self.error = None
        self.resultado = None

    def update(self, mensaje: str, fraccion: float):
        self.mensaje = mensaje
        self.fraccion = fraccion

    def set_done(self, resultado):
        self.completado = True
        self.resultado = resultado

    def set_error(self, error):
        self.completado = True
        self.error = error


class MainApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Orodelti - Automatización de Reportes SAP"
        self.page.window_width = 900
        self.page.window_height = 600
        self.page.window_min_width = 800
        self.page.window_min_height = 550
        self.page.theme_mode = ft.ThemeMode.LIGHT           # modo claro
        self.page.theme = ft.Theme(
            color_scheme_seed="#00BCD4",                    # cyan
            use_material3=True,
        )
        self.page.bgcolor = "#E0F7FA"                       # fondo aguamarina claro
        self.page.padding = 0

        self.selected_file = None
        self.processing = False

        # Servicio
        self.repo = HanaRepository(
            host='10.171.69.154',
            port=30015,
            user='B1ADMIN',
            password='0R0d31t1**'
        )
        self.service = ReportService(self.repo)

        # ---------- Barra superior (AppBar) ----------
        self.appbar = ft.AppBar(
            leading=ft.Icon(ft.Icons.ANALYTICS_OUTLINED, color=ft.Colors.WHITE),
            leading_width=40,
            title=ft.Text("Automatización de Reportes SAP", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            center_title=False,
            bgcolor="#00ACC1",      # cyan intenso
            elevation=4,
        )

        # ---------- Menú lateral ----------
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=180,
            group_alignment=-0.9,
            bgcolor="#00BCD4",           # cyan medio vibrante
            indicator_color="#FFD54F",   # amarillo brillante (indicador)
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.FILE_UPLOAD_OUTLINED,
                    selected_icon=ft.Icons.FILE_UPLOAD,
                    label="Generar Reporte"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Configuración",
                    disabled=True,
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.INFO_OUTLINED,
                    selected_icon=ft.Icons.INFO,
                    label="Acerca de",
                ),
            ],
            on_change=self.nav_changed,
        )

        # ---------- Contenido principal ----------
        self.file_icon = ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=80, color="#80DEEA")
        self.file_text = ft.Text("Ningún archivo seleccionado", size=16, italic=True, color="#607D8B")
        self.select_btn = ft.ElevatedButton(
            "Seleccionar archivo Excel",
            icon=ft.Icons.FOLDER_OPEN,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                bgcolor="#00BCD4",
                color=ft.Colors.WHITE,
            ),
            on_click=self.seleccionar_archivo,
        )
        self.file_picker_container = ft.Container(
            content=ft.Column(
                [self.file_icon, self.file_text, self.select_btn],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            border=ft.Border.all(2, "#4DD0E1"),      # borde cyan claro
            border_radius=12,
            padding=30,
            bgcolor=ft.Colors.WHITE,                 # tarjeta blanca
            width=600,
            alignment=ft.Alignment.CENTER,
        )

        self.generate_btn = ft.FilledButton(
            "Generar Reporte",
            icon=ft.Icons.PLAY_ARROW,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                bgcolor="#FF7043",                   # naranja coral
                color=ft.Colors.WHITE,
            ),
            disabled=True,
            on_click=self.generar_reporte,
        )

        self.progress_bar = ft.ProgressBar(width=400, value=0, visible=False, color="#00ACC1")
        self.progress_percent = ft.Text("0%", size=12, weight=ft.FontWeight.BOLD, visible=False, color="#37474F")
        self.status_text = ft.Text("", size=14, visible=False, color="#37474F")

        self.main_column = ft.Column(
            [
                ft.Text("Generación de Reportes de Compras y Traslados", size=22,
                        weight=ft.FontWeight.BOLD, color="#37474F"),
                ft.Divider(height=20, thickness=1, color="#4DD0E1"),
                self.file_picker_container,
                ft.Row([self.generate_btn], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([self.progress_bar, self.progress_percent], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                self.status_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.page.add(
            ft.Row(
                [
                    self.nav_rail,
                    ft.VerticalDivider(width=1, color="#4DD0E1"),
                    ft.Container(content=self.main_column, expand=True, padding=20),
                ],
                expand=True,
            )
        )
        self.page.add(self.appbar)
        self.page.update()

    # ---------- Eventos ----------
    def nav_changed(self, e):
        if e.control.selected_index == 2:
            self.mostrar_acerca_de()

    def mostrar_acerca_de(self):
        dlg = ft.AlertDialog(
            title=ft.Text("Acerca de"),
            content=ft.Text("Automatización de Reportes SAP v2.0\n\nDesarrollado para Orodelti."),
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def seleccionar_archivo(self, e):
        if self.processing:
            return
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        ruta = filedialog.askopenfilename(
            title="Selecciona tu reporte SAP",
            filetypes=[("Archivos Excel", "*.xlsx"), ("Todos los archivos", "*.*")]
        )
        root.attributes('-topmost', False)
        root.destroy()
        if ruta:
            self.selected_file = ruta
            self.file_text.value = f"📄 {os.path.basename(ruta)}"
            self.file_text.color = "#37474F"                     # texto oscuro
            self.file_icon.name = ft.Icons.INSERT_DRIVE_FILE
            self.file_icon.color = "#00BCD4"
            self.generate_btn.disabled = False
            self.status_text.visible = False
            self.progress_bar.visible = False
            self.progress_percent.visible = False
            self.page.update()

    def generar_reporte(self, e):
        if not self.selected_file or self.processing:
            return

        self.processing = True
        self.select_btn.disabled = True
        self.generate_btn.disabled = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_percent.visible = True
        self.progress_percent.value = "0%"
        self.status_text.visible = True
        self.status_text.value = "Iniciando..."
        self.page.update()

        reporter = ProgressReporter()

        def run_service():
            try:
                resultado = self.service.transformar(
                    self.selected_file,
                    progress_callback=lambda msg, frac: reporter.update(msg, frac)
                )
                reporter.set_done(resultado)
            except Exception as ex:
                reporter.set_error(ex)

        thread = threading.Thread(target=run_service, daemon=True)
        thread.start()

        async def update_progress():
            while not reporter.completado:
                self.status_text.value = reporter.mensaje
                self.progress_bar.value = reporter.fraccion
                self.progress_percent.value = f"{int(reporter.fraccion * 100)}%"
                self.page.update()
                await asyncio.sleep(0.1)

            self.processing = False
            self.select_btn.disabled = False
            self.generate_btn.disabled = False
            if reporter.error:
                self.status_text.value = f"Error: {reporter.error}"
                self.progress_bar.color = ft.Colors.RED
                self.progress_bar.value = 1
                self.progress_percent.value = "100%"
            else:
                self.status_text.value = "¡Reporte generado exitosamente!"
                self.progress_bar.color = "#66BB6A"
                self.progress_bar.value = 1
                self.progress_percent.value = "100%"
                self.page.dialog = ft.AlertDialog(
                    title=ft.Text("Éxito"),
                    content=ft.Text(
                        f"Archivo: {os.path.basename(self.selected_file)}\n"
                        f"Hojas creadas: {', '.join(reporter.resultado['hojas'])}\n"
                        f"Saldos iniciales: {len(reporter.resultado['saldos_iniciales'])} artículos"
                    ),
                )
                self.page.dialog.open = True
            self.page.update()

        self.page.run_task(update_progress)


def main():
    ft.app(target=MainApp, name="Orodelti - Reportes SAP")