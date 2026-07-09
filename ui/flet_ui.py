import flet as ft
import threading
import os
import asyncio
import random
import tkinter as tk
from tkinter import filedialog
from application.report_service import ReportService
from infrastructure.hana_repository import HanaRepository


# ---------------------------------------------------------------------------
# Paleta "Tech Dark · Aurora Glass"
# ---------------------------------------------------------------------------
BG_BASE = "#0A0E1A"
BG_CARD = "#141B2D"
BG_CARD_SOFT = "#1B2438"
BORDER_SOFT = "#2A3650"
ACCENT_A = "#6366F1"     # índigo
ACCENT_B = "#22D3EE"     # cian
ACCENT_C = "#A855F7"     # violeta (aurora)
SUCCESS = "#34D399"
ERROR = "#F87171"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#8AA0C0"
TEXT_MUTED = "#5B6B85"

WIN_W, WIN_H = 980, 660


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
        self.page.window.width = WIN_W
        self.page.window.height = WIN_H
        self.page.window.min_width = 860
        self.page.window.min_height = 600
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(color_scheme_seed=ACCENT_A, use_material3=True)
        self.page.bgcolor = BG_BASE
        self.page.padding = 0

        self.selected_file = None
        self.processing = False

        # Servicio: la conexión a HANA se hace en segundo plano (ver _init_backend)
        # para que la ventana se muestre instantáneamente sin esperar la red.
        self.repo = None
        self.service = None
        self.backend_ready = False
        self.backend_error = None

        # ================= FONDO: AURORA + PARTÍCULAS =================
        self.aurora_blobs = []
        aurora_specs = [
            (ACCENT_A, 40, 20, 300),
            (ACCENT_B, WIN_W - 360, WIN_H - 300, 340),
            (ACCENT_C, WIN_W / 2 - 150, WIN_H / 2 - 150, 300),
        ]
        for color, left, top, size in aurora_specs:
            blob = ft.Container(
                width=size,
                height=size,
                left=left,
                top=top,
                border_radius=size,
                gradient=ft.RadialGradient(
                    center=ft.Alignment.CENTER,
                    radius=0.5,
                    colors=[
                        ft.Colors.with_opacity(0.22, color),
                        ft.Colors.with_opacity(0.0, color),
                    ],
                ),
                blur=40,
                animate_position=ft.Animation(8000, ft.AnimationCurve.EASE_IN_OUT),
                animate_opacity=ft.Animation(8000, ft.AnimationCurve.EASE_IN_OUT),
                opacity=0.6,
            )
            self.aurora_blobs.append(blob)
        self._aurora_bases = [(l, t) for _, l, t, _ in aurora_specs]

        self.particles = []
        for _ in range(24):
            size = random.uniform(3.0, 6.0)
            p_color = random.choice([ACCENT_B, ACCENT_A, "#FFFFFF"])
            particle = ft.Container(
                width=size,
                height=size,
                left=random.uniform(10, WIN_W - 10),
                top=random.uniform(10, WIN_H - 10),
                border_radius=50,
                bgcolor=ft.Colors.with_opacity(random.uniform(0.4, 0.7), p_color),
                shadow=ft.BoxShadow(
                    blur_radius=10, spread_radius=1,
                    color=ft.Colors.with_opacity(0.55, p_color),
                    offset=ft.Offset(0, 0),
                ),
                animate_position=ft.Animation(
                    int(random.uniform(5000, 9000)), ft.AnimationCurve.EASE_IN_OUT
                ),
                animate_opacity=ft.Animation(3000, ft.AnimationCurve.EASE_IN_OUT),
            )
            self.particles.append(particle)

        self.background_layer = ft.Container(
            expand=True,
            bgcolor=BG_BASE,
            content=ft.Stack([*self.aurora_blobs, *self.particles], expand=True),
        )

        # ================= BARRA SUPERIOR (glass) =================
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
            shadow=ft.BoxShadow(
                blur_radius=22, spread_radius=1,
                color=ft.Colors.with_opacity(0.55, ACCENT_B),
                offset=ft.Offset(0, 0),
            ),
        )

        # Badge de estado de conexión a SAP HANA (se actualiza en _init_backend)
        self.hana_dot = ft.Container(
            width=7, height=7, border_radius=10, bgcolor="#FBBF24",
            shadow=ft.BoxShadow(blur_radius=10, color="#FBBF24"),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )
        self.hana_text = ft.Text("Conectando a SAP HANA...", size=11, color="#FBBF24",
                                  weight=ft.FontWeight.W_600)
        self.hana_badge = ft.Container(
            padding=ft.Padding(10, 5, 10, 5),
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.12, "#FBBF24"),
            content=ft.Row([self.hana_dot, self.hana_text], spacing=6, tight=True),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )

        self.top_bar = ft.Container(
            padding=ft.Padding(24, 16, 24, 16),
            bgcolor=ft.Colors.with_opacity(0.35, BG_CARD),
            blur=25,
            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.15, "#FFFFFF"))),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            logo_badge,
                            ft.Column(
                                [
                                    ft.Text("Automatización de Reportes SAP", size=17,
                                            weight=ft.FontWeight.W_700, color=TEXT_PRIMARY),
                                    ft.Text("Orodelti · Compras y Traslados", size=12, color=TEXT_SECONDARY),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=14,
                    ),
                    self.hana_badge,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

        # ================= MENÚ LATERAL =================
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=96,
            min_extended_width=180,
            group_alignment=-0.9,
            bgcolor=ft.Colors.with_opacity(0.35, BG_CARD),
            indicator_color=ft.Colors.with_opacity(0.18, ACCENT_B),
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

        # ================= TARJETA DE ARCHIVO (glass) =================
        self.file_icon_badge = ft.Container(
            width=72, height=72, border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.10, ACCENT_B),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ACCENT_B)),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=34, color=ACCENT_B),
            shadow=ft.BoxShadow(blur_radius=28, spread_radius=-2,
                                 color=ft.Colors.with_opacity(0.45, ACCENT_B), offset=ft.Offset(0, 0)),
            animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        )
        self.file_text = ft.Text("Ningún archivo seleccionado", size=14, color=TEXT_SECONDARY)
        self.file_subtext = ft.Text("Formatos admitidos: .xlsx", size=11, color=TEXT_MUTED)
        self.select_btn = self._build_gradient_button(
            text="Seleccionar archivo Excel",
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            on_click=self.seleccionar_archivo,
            colors=[ACCENT_A, ACCENT_B],
            glow_color=ACCENT_B,
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
            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, "#FFFFFF")),
            border_radius=20,
            padding=36,
            bgcolor=ft.Colors.with_opacity(0.06, "#FFFFFF"),
            blur=30,
            width=560,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(
                blur_radius=30, spread_radius=-6,
                color=ft.Colors.with_opacity(0.5, "#000000"),
                offset=ft.Offset(0, 12),
            ),
        )

        self.generate_btn = self._build_gradient_button(
            text="Generar Reporte",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=self.generar_reporte,
            colors=["#FB923C", "#F97316"],
            glow_color="#F97316",
            disabled=True,
        )

        # ================= PROGRESO =================
        self.progress_bar = ft.ProgressBar(
            width=460, value=0, visible=False,
            color=ACCENT_B, bgcolor=BG_CARD_SOFT, border_radius=10,
        )
        self.progress_glow_wrap = ft.Container(
            content=self.progress_bar,
            border_radius=10,
            shadow=None,
            animate=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
        )
        self.progress_percent = ft.Text("0%", size=12, weight=ft.FontWeight.W_700,
                                         visible=False, color=TEXT_PRIMARY)

        self.status_icon = ft.Icon(ft.Icons.SYNC_ROUNDED, size=16, color=ACCENT_B, visible=False)
        self.status_icon_wrap = ft.Container(
            content=self.status_icon,
            visible=False,
            shadow=None,
            animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        )
        self.status_text = ft.Text("", size=13, visible=False, color=TEXT_SECONDARY)

        self.success_ring = ft.Container(
            width=64, height=64, border_radius=999,
            border=ft.Border.all(3, SUCCESS),
            opacity=0, scale=1, visible=False,
            animate_opacity=ft.Animation(900, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(900, ft.AnimationCurve.EASE_OUT),
        )

        self.main_column = ft.Column(
            [
                self.file_picker_container,
                ft.Container(height=8),
                ft.Row([self.generate_btn], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=4),
                ft.Row([self.progress_glow_wrap, self.progress_percent],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=12),
                ft.Stack(
                    [
                        ft.Row([self.success_ring], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([self.status_icon_wrap, self.status_text],
                               alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                    ],
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=18,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # ================= LAYOUT + TRANSICIÓN DE ENTRADA =================
        self.app_shell = ft.Column(
            [
                self.top_bar,
                ft.Row(
                    [
                        self.nav_rail,
                        ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.3, BORDER_SOFT)),
                        ft.Container(content=self.main_column, expand=True, padding=24),
                    ],
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

        self.fade_wrapper = ft.Container(
            content=self.app_shell,
            expand=True,
            opacity=0,
            scale=0.97,
            animate_opacity=ft.Animation(700, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(700, ft.AnimationCurve.EASE_OUT),
        )

        self.page.add(
            ft.Stack([self.background_layer, self.fade_wrapper], expand=True)
        )
        self.page.update()

        # Disparar animaciones de fondo y transición de entrada
        self.page.run_task(self._fade_in)
        self.page.run_task(self._animate_particles)
        self.page.run_task(self._animate_aurora)

        # Conectar a SAP HANA en segundo plano (no bloquea la apertura de la ventana)
        threading.Thread(target=self._init_backend, daemon=True).start()

    def _init_backend(self):
        try:
            self.repo = HanaRepository(
                host='10.171.69.154',
                port=30015,
                user='B1ADMIN',
                password='0R0d31t1**'
            )
            self.service = ReportService(self.repo)
            self.backend_ready = True
            self.hana_dot.bgcolor = SUCCESS
            self.hana_dot.shadow = ft.BoxShadow(blur_radius=10, color=SUCCESS)
            self.hana_text.value = "SAP HANA conectado"
            self.hana_text.color = SUCCESS
            self.hana_badge.bgcolor = ft.Colors.with_opacity(0.12, SUCCESS)
        except Exception as ex:
            self.backend_error = ex
            self.hana_dot.bgcolor = ERROR
            self.hana_dot.shadow = ft.BoxShadow(blur_radius=10, color=ERROR)
            self.hana_text.value = "Sin conexión a SAP HANA"
            self.hana_text.color = ERROR
            self.hana_badge.bgcolor = ft.Colors.with_opacity(0.12, ERROR)
        self.page.update()

    # ---------- Animaciones de fondo ----------
    async def _fade_in(self):
        await asyncio.sleep(0.05)
        self.fade_wrapper.opacity = 1
        self.fade_wrapper.scale = 1
        self.fade_wrapper.update()

    async def _animate_particles(self):
        while True:
            for p in self.particles:
                p.left = random.uniform(10, WIN_W - 10)
                p.top = random.uniform(10, WIN_H - 10)
                p.opacity = random.uniform(0.35, 0.65)
            try:
                self.background_layer.update()
            except Exception:
                return
            await asyncio.sleep(random.uniform(5, 8))

    async def _animate_aurora(self):
        while True:
            for blob, (base_l, base_t) in zip(self.aurora_blobs, self._aurora_bases):
                blob.left = base_l + random.uniform(-40, 40)
                blob.top = base_t + random.uniform(-30, 30)
                blob.opacity = random.uniform(0.45, 0.65)
            try:
                self.background_layer.update()
            except Exception:
                return
            await asyncio.sleep(random.uniform(7, 10))

    async def _pulse_progress_glow(self):
        toggle = False
        while self.processing:
            toggle = not toggle
            self.progress_glow_wrap.shadow = ft.BoxShadow(
                blur_radius=26 if toggle else 12,
                spread_radius=-2,
                color=ft.Colors.with_opacity(0.5 if toggle else 0.25, self.progress_bar.color),
                offset=ft.Offset(0, 0),
            )
            try:
                self.progress_glow_wrap.update()
            except Exception:
                return
            await asyncio.sleep(0.6)
        self.progress_glow_wrap.shadow = None
        try:
            self.progress_glow_wrap.update()
        except Exception:
            pass

    async def _play_success_ping(self):
        self.success_ring.visible = True
        self.success_ring.scale = 1
        self.success_ring.opacity = 0.85
        self.success_ring.update()
        await asyncio.sleep(0.05)
        self.success_ring.scale = 2.3
        self.success_ring.opacity = 0
        self.success_ring.update()
        await asyncio.sleep(1)
        self.success_ring.visible = False
        self.success_ring.update()

    # ---------- Helpers de UI ----------
    def _build_gradient_button(self, text, icon, on_click, colors, glow_color, disabled=False):
        """Botón con degradado, glow permanente y realce al pasar el mouse."""
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
            animate_scale=ft.Animation(250, ft.AnimationCurve.EASE_OUT_CUBIC),
            scale=1.0,
            data=glow_color,
            shadow=None if disabled else ft.BoxShadow(
                blur_radius=18, spread_radius=-4,
                color=ft.Colors.with_opacity(0.35, glow_color),
                offset=ft.Offset(0, 4),
            ),
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_button_hover if not disabled else None,
        )
        return btn

    def _on_button_hover(self, e: ft.ControlEvent):
        btn = e.control
        glow_color = btn.data
        if e.data == "true":
            btn.scale = 1.05
            btn.shadow = ft.BoxShadow(
                blur_radius=28, spread_radius=-2,
                color=ft.Colors.with_opacity(0.6, glow_color),
                offset=ft.Offset(0, 8),
            )
        else:
            btn.scale = 1.0
            btn.shadow = ft.BoxShadow(
                blur_radius=18, spread_radius=-4,
                color=ft.Colors.with_opacity(0.35, glow_color),
                offset=ft.Offset(0, 4),
            )
        self.page.update()

    def _set_button_disabled(self, btn: ft.Container, disabled: bool, on_click=None):
        btn.disabled = disabled
        btn.opacity = 0.4 if disabled else 1.0
        btn.on_click = None if disabled else on_click
        if disabled:
            btn.shadow = None
        else:
            btn.shadow = ft.BoxShadow(
                blur_radius=18, spread_radius=-4,
                color=ft.Colors.with_opacity(0.35, btn.data),
                offset=ft.Offset(0, 4),
            )

    def _set_status(self, icon_name, color, text):
        self.status_icon.name = icon_name
        self.status_icon.color = color
        self.status_text.color = color
        self.status_icon_wrap.shadow = ft.BoxShadow(
            blur_radius=20, spread_radius=-2,
            color=ft.Colors.with_opacity(0.55, color),
            offset=ft.Offset(0, 0),
        )
        self.status_text.value = text

    # ---------- Eventos ----------
    def nav_changed(self, e):
        if e.control.selected_index == 2:
            self.mostrar_acerca_de()

    def mostrar_acerca_de(self):
        dlg = ft.AlertDialog(
            bgcolor=ft.Colors.with_opacity(0.85, BG_CARD),
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
        self.file_icon_badge.bgcolor = ft.Colors.with_opacity(0.10, SUCCESS)
        self.file_icon_badge.border = ft.Border.all(1, ft.Colors.with_opacity(0.35, SUCCESS))
        self.file_icon_badge.shadow = ft.BoxShadow(
            blur_radius=28, spread_radius=-2,
            color=ft.Colors.with_opacity(0.5, SUCCESS), offset=ft.Offset(0, 0),
        )
        self._set_button_disabled(self.generate_btn, False, self.generar_reporte)
        self.status_text.visible = False
        self.status_icon_wrap.visible = False
        self.progress_bar.visible = False
        self.progress_percent.visible = False
        self.success_ring.visible = False
        self.page.update()

    def generar_reporte(self, e):
        if not self.selected_file or self.processing:
            return
        if not self.backend_ready:
            self._set_status(
                ft.Icons.HOURGLASS_TOP_ROUNDED, "#FBBF24",
                "Aún conectando con SAP HANA, espera un momento...",
            )
            self.status_text.visible = True
            self.status_icon_wrap.visible = True
            self.page.update()
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
        self.status_icon_wrap.visible = True
        self._set_status(ft.Icons.SYNC_ROUNDED, ACCENT_B, "Iniciando...")
        self.page.update()
        self.page.run_task(self._pulse_progress_glow)

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
                self.progress_bar.color = ERROR
                self.progress_bar.value = 1
                self.progress_percent.value = "100%"
                self._set_status(ft.Icons.ERROR_OUTLINE_ROUNDED, ERROR, f"Error: {reporter.error}")
            else:
                self.progress_bar.color = SUCCESS
                self.progress_bar.value = 1
                self.progress_percent.value = "100%"
                self._set_status(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, SUCCESS, "¡Reporte generado exitosamente!")
                self.page.run_task(self._play_success_ping)
                self.page.dialog = ft.AlertDialog(
                    bgcolor=ft.Colors.with_opacity(0.9, BG_CARD),
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