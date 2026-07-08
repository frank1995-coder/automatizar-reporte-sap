import tkinter as tk
from tkinter import filedialog, messagebox
import sys

def pedir_archivo() -> str:
    root = tk.Tk()
    root.withdraw()
    ruta = filedialog.askopenfilename(
        title="Selecciona tu reporte SAP",
        filetypes=[("Archivos Excel", "*.xlsx"), ("Todos los archivos", "*.*")]
    )
    root.destroy()
    if not ruta:
        sys.exit("❌ No se seleccionó ningún archivo.")
    return ruta

def mostrar_mensaje(msg: str):
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Listo", msg)
    root.destroy()