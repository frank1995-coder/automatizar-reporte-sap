import flet as ft
import threading
import os
import asyncio
import tkinter as tk
from tkinter import filedialog
from application.report_service import ReportService
from infrastructure.hana_repository import HanaRepository



# Paleta "Tech Dark"

BG_BASE = "#0B1120"          # fondo general (slate-950)
BG_CARD = "#141B2D"          # tarjetas
BG_CARD_SOFT = "#1B2438"     # tarjetas secundarias / hover
BORDER_SOFT = "#26324A"      # bordes sutiles
ACCENT_A = "#6366F1"         # índigo
ACCENT_B = "#22D3EE"         # cian
SUCCESS = "#34D399"
ERROR = "#F87171"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#8AA0C0"
TEXT_MUTED = "#5B6B85"

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
        self.page.window.width = 980
        self.page.window.height = 660
        self.page.window.min_width = 860
        self.page.window.min_height = 600
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(
            color_scheme_seed=ACCENT_A,
            use_material3=True,
        )
        self.page.bgcolor = BG_BASE
        self.page.padding = 0
        self.page.fonts = {}

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

        # ---------- Barra superior ----------
        logo_badge = ft.Container(
            width=42,
            height=42,
            border_radius=12,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[ACCENT_A, ACCENT_B],
            ),
            content=ft.Icon(ft.Icons.BOLT_ROUNDED, color=ft.Colors.WHITE, size=22),
            alignment=ft.Alignment.CENTER,
        )

        self.top_bar = ft.Container(
            padding=ft.Padding(24, 16, 24, 16),
            bgcolor=BG_CARD,
            border=ft.Border(bottom=ft.BorderSide(1, BORDER_SOFT)),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            logo_badge,
                            ft.Column(
                                [
                                    ft.Text(
                                        "Automatización de Reportes SAP",
                                        size=17,
                                        weight=ft.FontWeight.W_700,
                                        color=TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        "Orodelti · Compras y Traslados",
                                        size=12,
                                        color=TEXT_SECONDARY,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=14,
                    ),
                    ft.Container(
                        padding=ft.Padding(10, 5, 10, 5),
                        border_radius=20,
                        bgcolor=ft.Colors.with_opacity(0.12, SUCCESS),
                        content=ft.Row(
                            [
                                ft.Container(width=7, height=7, border_radius=10, bgcolor=SUCCESS),
                                ft.Text("SAP HANA conectado", size=11, color=SUCCESS, weight=ft.FontWeight.W_600),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

        # ---------- Menú lateral ----------
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=96,
            min_extended_width=180,
            group_alignment=-0.9,
            bgcolor=BG_CARD,
            indicator_color=ft.Colors.with_opacity(0.15, ACCENT_B),
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.FILE_UPLOAD_OUTLINED,
                    selected_icon=ft.Icon(ft.Icons.FILE_UPLOAD, color=ACCENT_B),
                    label="Generar",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Config.",
                    disabled=True,
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.INFO_OUTLINED,
                    selected_icon=ft.Icon(ft.Icons.INFO, color=ACCENT_B),
                    label="Acerca de",
                ),
            ],
            on_change=self.nav_changed,
        )

        # -- Tarjeta: selector de archivo 
        self.file_icon_badge = ft.Container(
            width=72,
            height=72,
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.08, ACCENT_B),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ACCENT_B)),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=34, color=ACCENT_B),
        )
        self.file_text = ft.Text(
            "Ningún archivo seleccionado",
            size=14,
            color=TEXT_SECONDARY,
        )
        self.file_subtext = ft.Text(
            "Formatos admitidos: .xlsx",
            size=11,
            color=TEXT_MUTED,
        )
        self.select_btn = self._build_gradient_button(
            text="Seleccionar archivo Excel",
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            on_click=self.seleccionar_archivo,
            colors=[ACCENT_A, ACCENT_B],
        )

        self.file_picker_container = ft.Container(
            content=ft.Column(
                [
                    self.file_icon_badge,
                    ft.Container(height=6),
                    self.file_text,
                    self.file_subtext,
                    ft.Container(height=10),
                    self.select_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            border=ft.Border.all(1, BORDER_SOFT),
            border_radius=18,
            padding=36,
            bgcolor=BG_CARD,
            width=560,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(
                blur_radius=24,
                spread_radius=-4,
                color=ft.Colors.with_opacity(0.4, "#000000"),
                offset=ft.Offset(0, 8),
            ),
        )

        self.generate_btn = self._build_gradient_button(
            text="Generar Reporte",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=self.generar_reporte,
            colors=["#FB923C", "#F97316"],
            disabled=True,
        )

        self.progress_bar = ft.ProgressBar(
            width=460,
            value=0,
            visible=False,
            color=ACCENT_B,
            bgcolor=BG_CARD_SOFT,
            border_radius=10,
        )
        self.progress_percent = ft.Text(
            "0%", size=12, weight=ft.FontWeight.W_700, visible=False, color=TEXT_PRIMARY,
        )
        self.status_icon = ft.Icon(ft.Icons.SYNC_ROUNDED, size=16, color=ACCENT_B, visible=False)
        self.status_text = ft.Text("", size=13, visible=False, color=TEXT_SECONDARY)

        self.main_column = ft.Column(
            [
                self.file_picker_container,
                ft.Container(height=8),
                ft.Row([self.generate_btn], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=4),
                ft.Row([self.progress_bar, self.progress_percent],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=12),
                ft.Row([self.status_icon, self.status_text],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=18,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.page.add(
            ft.Column(
                [
                    self.top_bar,
                    ft.Row(
                        [
                            self.nav_rail,
                            ft.VerticalDivider(width=1, color=BORDER_SOFT),
                            ft.Container(content=self.main_column, expand=True, padding=24),
                        ],
                        expand=True,
                    ),
                ],
                spacing=0,
                expand=True,
            )
        )
        self.page.update()

    # ---------- Helpers de UI ----------
    def _build_gradient_button(self, text, icon, on_click, colors, disabled=False):
        """Botón con degradado, escala al pasar el mouse y sombra."""
        content_row = ft.Row(
            [ft.Icon(icon, color=ft.Colors.WHITE, size=18),
             ft.Text(text, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
            tight=True,
        )
        btn = ft.Container(
            content=content_row,
            padding=ft.Padding(24, 14, 24, 14),
            border_radius=12,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.CENTER_LEFT,
                end=ft.Alignment.CENTER_RIGHT,
                colors=colors,
            ),
            ink=True,
            on_click=None if disabled else on_click,
            opacity=0.4 if disabled else 1.0,
            disabled=disabled,
            animate_opacity=200,
            alignment=ft.Alignment.CENTER,
            # ---- Efecto hover: escala y sombra ----
            animate_scale=ft.Animation(250, "easeOutCubic"),
            scale=1.0,
            shadow=None,
            on_hover=self._on_button_hover if not disabled else None,
        )
        return btn

    def _on_button_hover(self, e: ft.ControlEvent):
        """Aplica escala y sombra cuando el mouse entra/sale del botón."""
        btn = e.control
        if e.data == "true":  # mouse entrando
            btn.scale = 1.05
            btn.shadow = ft.BoxShadow(
                blur_radius=20,
                spread_radius=-2,
                color=ft.Colors.with_opacity(0.35, ACCENT_B),
                offset=ft.Offset(0, 6),
            )
        else:  # mouse saliendo
            btn.scale = 1.0
            btn.shadow = None
        self.page.update()

    def _set_button_disabled(self, btn: ft.Container, disabled: bool, on_click=None):
        btn.disabled = disabled
        btn.opacity = 0.4 if disabled else 1.0
        btn.on_click = None if disabled else on_click

    # ---------- Eventos ----------
    def nav_changed(self, e):
        if e.control.selected_index == 2:
            self.mostrar_acerca_de()

    def mostrar_acerca_de(self):
        dlg = ft.AlertDialog(
            bgcolor=BG_CARD,
            title=ft.Text("Acerca de", color=TEXT_PRIMARY),
            content=ft.Text(
                "Automatización de Reportes SAP v2.0\n\nDesarrollado para Orodelti.",
                color=TEXT_SECONDARY,
            ),
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
            title="Selecciona tu reporte de SAP",
            filetypes=[("Archivos Excel", "*.xlsx"), ("Todos los archivos", "*.*")]
        )
        root.attributes('-topmost', False)
        root.destroy()
        if not ruta:
            return
        self.selected_file = ruta
        self.file_text.value = os.path.basename(ruta)
        self.file_text.color = TEXT_PRIMARY
        self.file_subtext.value = "Archivo listo para procesar"
        self.file_subtext.color = SUCCESS
        self.file_icon_badge.content.name = ft.Icons.TASK_OUTLINED
        self.file_icon_badge.content.color = SUCCESS
        self.file_icon_badge.bgcolor = ft.Colors.with_opacity(0.08, SUCCESS)
        self.file_icon_badge.border = ft.Border.all(1, ft.Colors.with_opacity(0.3, SUCCESS))
        self._set_button_disabled(self.generate_btn, False, self.generar_reporte)
        self.status_text.visible = False
        self.status_icon.visible = False
        self.progress_bar.visible = False
        self.progress_percent.visible = False
        self.page.update()

    def generar_reporte(self, e):
        if not self.selected_file or self.processing:
            return

        self.processing = True
        self._set_button_disabled(self.select_btn, True)
        self._set_button_disabled(self.generate_btn, True)
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_bar.color = ACCENT_B
        self.progress_percent.visible = True
        self.progress_percent.value = "0%"
        self.status_text.visible = True
        self.status_text.value = "Iniciando..."
        self.status_icon.visible = True
        self.status_icon.name = ft.Icons.SYNC_ROUNDED
        self.status_icon.color = ACCENT_B
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
            self._set_button_disabled(self.select_btn, False, self.seleccionar_archivo)
            self._set_button_disabled(self.generate_btn, False, self.generar_reporte)

            if reporter.error:
                self.status_text.value = f"Error: {reporter.error}"
                self.status_text.color = ERROR
                self.status_icon.name = ft.Icons.ERROR_OUTLINE_ROUNDED
                self.status_icon.color = ERROR
                self.progress_bar.color = ERROR
                self.progress_bar.value = 1
                self.progress_percent.value = "100%"
            else:
                self.status_text.value = "¡Reporte generado exitosamente!"
                self.status_text.color = SUCCESS
                self.status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                self.status_icon.color = SUCCESS
                self.progress_bar.color = SUCCESS
                self.progress_bar.value = 1
                self.progress_percent.value = "100%"
                self.page.dialog = ft.AlertDialog(
                    bgcolor=BG_CARD,
                    title=ft.Row(
                        [ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=SUCCESS), ft.Text("Éxito", color=TEXT_PRIMARY)],
                        spacing=8,
                    ),
                    content=ft.Text(
                        f"Archivo: {os.path.basename(self.selected_file)}\n"
                        f"Hojas creadas: {', '.join(reporter.resultado['hojas'])}\n"
                        f"Saldos iniciales: {len(reporter.resultado['saldos_iniciales'])} artículos",
                        color=TEXT_SECONDARY,
                    ),
                )
                self.page.dialog.open = True
            self.page.update()

        self.page.run_task(update_progress)


def main():
    ft.app(target=MainApp, name="Orodelti - Reportes SAP")


if __name__ == "__main__":
    main()