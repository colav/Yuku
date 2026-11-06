import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import yuku.minciencias_convocations as mc

FIXTURES = Path(__file__).parent / "fixtures" / "minciencias_convocatorias"


def tabla(nombre):
    with (FIXTURES / "tablas_reales.json").open(encoding="utf-8") as archivo:
        return json.load(archivo)[nombre]


def fuente(numero, año, pdf=Path("convocatoria.pdf")):
    return mc.Fuente(
        pdf=pdf,
        relativa=pdf.name,
        sha256="0" * 64,
        convocatoria=mc.Convocatoria(numero, año),
        clase="grupos",
    )


def extraer_con_tabla(extractor, numero, año, datos):
    """Ejecuta un extractor por palabras con coordenadas reales de una página."""
    palabras = {datos["pagina"]: [tuple(palabra) for palabra in datos["palabras"]]}
    bordes = (datos["horizontales"], datos["verticales"])
    with mock.patch.object(mc, "palabras_tsv", return_value=palabras), mock.patch.object(
        mc, "bordes_pagina", return_value=bordes
    ):
        return {
            fila.codigo: fila
            for fila in extractor(fuente(numero, año), Path("/nonexistent"))
        }


class UnirFragmentosTest(unittest.TestCase):
    def test_reverts_typographic_hyphenation(self):
        self.assertEqual(
            mc.unir_fragmentos(["UNIVERSIDAD DEL ROSA-", "RIO"]),
            "UNIVERSIDAD DEL ROSARIO",
        )

    def test_joins_words_cut_without_hyphen(self):
        self.assertEqual(
            mc.unir_fragmentos(
                ["CENTRO NACIONAL DE", "INVESTIGACIONE", "S DE CAFÉ", "(CENICAFÉ)"],
                [False, True, False, False],
            ),
            "CENTRO NACIONAL DE INVESTIGACIONES DE CAFÉ (CENICAFÉ)",
        )

    def test_keeps_literal_hyphen_of_open_line(self):
        self.assertEqual(
            mc.unir_fragmentos(
                ["FUNDACIÓN CARDIOINFANTIL-", "INSTITUTO DE CARDIOLOGÍA"],
                [True, False],
            ),
            "FUNDACIÓN CARDIOINFANTIL-INSTITUTO DE CARDIOLOGÍA",
        )

    def test_closed_lines_keep_previous_behaviour(self):
        fragmentos = ["UNIVERSIDAD DEL ROSA-", "RIO", "- SEDE"]
        self.assertEqual(
            mc.unir_fragmentos(fragmentos, [False, False, False]),
            mc.unir_fragmentos(fragmentos),
        )


class ElementosPaginaTest(unittest.TestCase):
    def test_marks_lines_without_trailing_space(self):
        pagina = ET.fromstring(
            '<page number="1" width="1000" height="1000">'
            '<text top="10" left="400" width="80" height="15">CENTRO </text>'
            '<text top="25" left="400" width="94" height="15">INVESTIGACIONE</text>'
            '<text top="40" left="400" width="94" height="15">CARDIOINFANTIL-</text>'
            '<text top="55" left="400" width="40" height="15">(CENICAFÉ)</text>'
            "</page>"
        )
        self.assertEqual(
            [(texto, abierta) for _, _, texto, abierta in mc.elementos_pagina(pagina)],
            [
                ("CENTRO", False),
                ("INVESTIGACIONE", True),
                ("CARDIOINFANTIL-", True),
                ("(CENICAFÉ)", False),
            ],
        )


class BordesPaginaTest(unittest.TestCase):
    SVG = (
        '<svg><defs><g id="glyph-0-1"><path d="M 0.5 0 L 0.5 -6.4 L 1.5 -6.4 Z"/></g>'
        "</defs>"
        '<path fill-rule="evenodd" fill="rgb(100%, 100%, 100%)" '
        'd="M 49.8 89.8 L 220.3 89.8 L 220.3 29.4 Z"/>'
        '<path fill-rule="evenodd" fill="rgb(0%, 0%, 0%)" '
        'd="M 81.8 113.9 L 134.6 113.9 L 134.6 113.4 L 81.8 113.4 Z"/>'
        '<path fill-rule="evenodd" fill="rgb(0%, 0%, 0%)" '
        'd="M 135.1 113.9 L 275.9 113.9 L 275.9 113.4 L 135.1 113.4 Z"/>'
        '<path fill-rule="nonzero" fill="rgb(0%, 0%, 0%)" '
        'd="M 134.6 113.4 L 134.6 160.0 L 135.1 160.0 L 135.1 113.4 Z"/>'
        '<path fill="rgb(0%, 0%, 0%)" transform="matrix(1,0,0,1,5,5)" '
        'd="M 10 300 L 400 300 L 400 300.5 L 10 300.5 Z"/>'
        "</svg>"
    )

    def test_reads_thin_filled_rules_and_merges_segments(self):
        def escribir_svg(comando):
            Path(comando[-1]).write_text(self.SVG, encoding="utf-8")
            return ""

        with tempfile.TemporaryDirectory() as temporal, mock.patch.object(
            mc, "ejecutar", side_effect=escribir_svg
        ):
            horizontales, verticales = mc.bordes_pagina(
                fuente(598, 2012), 4, Path(temporal)
            )
            self.assertEqual(list(Path(temporal).iterdir()), [])
        self.assertEqual([round(valor, 2) for valor in horizontales], [113.65])
        self.assertEqual([round(valor, 2) for valor in verticales], [134.85])

    def test_rejects_page_with_unexpected_columns(self):
        with mock.patch.object(mc, "bordes_pagina", return_value=([1.0, 2.0], [1.0, 2.0])):
            with self.assertRaisesRegex(RuntimeError, "bordes verticales"):
                mc.bordes_verticales_tabla(fuente(598, 2012), 4, Path("/nonexistent"))


class Extraer2012Test(unittest.TestCase):
    """Página 4 de 598-2012: códigos centrados y celdas de institución altas."""

    def setUp(self):
        self.filas = extraer_con_tabla(
            mc.extraer_grupos_2012, 598, 2012, tabla("598-2012")
        )

    def test_rows_follow_drawn_borders(self):
        self.assertEqual(
            self.filas["COL0000962"].instituciones,
            "CORPORACIÓN PARA INVESTIGACIONES BIOLÓGICAS - CIB; "
            "UNIVERSIDAD DE ANTIOQUIA - UDEA; UNIVERSIDAD DEL ROSARIO",
        )
        self.assertEqual(
            self.filas["COL0000953"].instituciones, "UNIVERSIDAD NACIONAL DE COLOMBIA"
        )
        self.assertEqual(
            self.filas["COL0000971"].instituciones, "UNIVERSIDAD NACIONAL DE COLOMBIA"
        )

    def test_name_and_leader_stay_in_their_row(self):
        fila = self.filas["COL0000962"]
        self.assertEqual(
            fila.nombre, "BIOLOGÍA CELULAR Y MOLECULAR CIB, U. DE A. U. DEL ROSARIO"
        )
        self.assertEqual(fila.lider, "JUAN GUILLERMO MCEWEN OCHOA")
        self.assertEqual(
            self.filas["COL0000971"].nombre, "BIOLOGÍA MOLECULAR TEÓRICA Y EVOLUTIVA"
        )

    def test_code_outside_table_rows_is_an_error(self):
        datos = tabla("598-2012")
        datos["horizontales"] = datos["horizontales"][:2]
        with self.assertRaisesRegex(RuntimeError, "fila propia"):
            extraer_con_tabla(mc.extraer_grupos_2012, 598, 2012, datos)


class Extraer2006Test(unittest.TestCase):
    """359-2006: tres columnas de institución entre el nombre y el líder."""

    def test_institution_columns_are_not_interleaved(self):
        filas = extraer_con_tabla(
            mc.extraer_grupos_2006, 359, 2006, tabla("359-2006-p47")
        )
        fila = filas["COL0014064"]
        self.assertEqual(
            fila.instituciones,
            "Corporación Para Investigaciones Biológicas; Universidad De Pamplona",
        )
        self.assertEqual(fila.nombre, "Genética y Bioquímica de Microorganismos")
        self.assertEqual(fila.lider, "Mauricio Corredor Rodríguez")
        self.assertEqual(fila.clasificacion, "A")

    def test_name_does_not_spill_into_institution(self):
        filas = extraer_con_tabla(
            mc.extraer_grupos_2006, 359, 2006, tabla("359-2006-p22")
        )
        fila = filas["COL0002671"]
        self.assertEqual(fila.nombre, "Comunicación, Periodismo y Sociedad")
        self.assertEqual(fila.instituciones, "Universidad De Antioquia")
        self.assertEqual(fila.lider, "Eduardo Domínguez Gómez")


@unittest.skipUnless(
    os.environ.get("YUKU_CONVOCATORIAS_DIR"),
    "definir YUKU_CONVOCATORIAS_DIR con la carpeta Convocatorias para la integración",
)
class ConvocatoriasPdfIntegrationTest(unittest.TestCase):
    """Extracción completa con los PDF oficiales (lenta, opcional)."""

    @classmethod
    def setUpClass(cls):
        raiz = Path(os.environ["YUKU_CONVOCATORIAS_DIR"])
        cls.fuentes = {
            item.convocatoria.etiqueta: item
            for item in mc.inventariar(raiz)[0]
            if item.clase == "grupos"
        }

    def extraer(self, etiqueta):
        with tempfile.TemporaryDirectory() as temporal:
            filas = mc.extraer_grupos(self.fuentes[etiqueta], Path(temporal))
        return {fila.codigo: fila for fila in filas}

    def test_598_2012(self):
        filas = self.extraer("598-2012")
        self.assertEqual(len(filas), mc.ESPERADOS_GRUPOS[(598, 2012)])
        self.assertEqual(
            filas["COL0000962"].instituciones,
            "CORPORACIÓN PARA INVESTIGACIONES BIOLÓGICAS - CIB; "
            "UNIVERSIDAD DE ANTIOQUIA - UDEA; UNIVERSIDAD DEL ROSARIO",
        )

    def test_359_2006(self):
        filas = self.extraer("359-2006")
        self.assertEqual(len(filas), mc.ESPERADOS_GRUPOS[(359, 2006)])
        self.assertEqual(
            filas["COL0014064"].instituciones,
            "Corporación Para Investigaciones Biológicas; Universidad De Pamplona",
        )

    def test_957_2024(self):
        filas = self.extraer("957-2024")
        self.assertEqual(len(filas), mc.ESPERADOS_GRUPOS[(957, 2024)])
        self.assertEqual(
            filas["COL0000336"].instituciones,
            "FEDERACIÓN NACIONAL DE CAFETEROS DE COLOMBIA - CENTRO NACIONAL DE "
            "INVESTIGACIONES DE CAFÉ (CENICAFÉ)",
        )
        self.assertIn(
            "FUNDACIÓN CARDIOINFANTIL-INSTITUTO DE CARDIOLOGÍA",
            filas["COL0160634"].instituciones,
        )


if __name__ == "__main__":
    unittest.main()
