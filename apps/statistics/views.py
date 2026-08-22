import io
from datetime import date
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import View

from apps.patients.models import IssueFinale
from .permissions import StatisticienRequiredMixin
from .services import periode_range, liste_unites, build_dashboard_context


class DashboardView(StatisticienRequiredMixin, View):
    """1. Épidémiologie – Dépistage (page d'accueil statistiques)."""
    template_name = 'statistics/dashboard.html'

    def get(self, request, *args, **kwargs):
        annee = request.GET.get('annee') or str(timezone.localdate().year)
        trimestre = request.GET.get('trimestre') or ''
        mois = request.GET.get('mois') or ''
        unite = request.GET.get('unite') or ''

        if mois:
            trimestre = ''

        debut, fin = periode_range(annee, trimestre if trimestre else None, mois if mois else None)

        context_ctx = build_dashboard_context(debut, fin, unite if unite else None)
        unites = liste_unites()

        context = {
            'active_nav': 'statistics',
            'annee': annee,
            'trimestre': trimestre,
            'mois': mois,
            'unite': unite,
            'debut': debut,
            'fin': fin,
            'unites': unites,
            'ep': context_ctx['epi'],
            'annee_choices': list(range(timezone.localdate().year - 5, timezone.localdate().year + 1)),
        }
        return render(request, self.template_name, context)


class CohorteView(StatisticienRequiredMixin, View):
    """2. Résultats de traitement – Cohorte trimestrielle (page dédiée)."""
    template_name = 'statistics/cohorte.html'

    def get(self, request, *args, **kwargs):
        annee = request.GET.get('annee') or str(timezone.localdate().year)
        trimestre = request.GET.get('trimestre') or ''
        mois = request.GET.get('mois') or ''
        unite = request.GET.get('unite') or ''

        if mois:
            trimestre = ''

        debut, fin = periode_range(annee, trimestre if trimestre else None, mois if mois else None)

        context_ctx = build_dashboard_context(debut, fin, unite if unite else None)
        unites = liste_unites()

        context = {
            'active_nav': 'statistics_cohorte',
            'annee': annee,
            'trimestre': trimestre,
            'mois': mois,
            'unite': unite,
            'debut': debut,
            'fin': fin,
            'unites': unites,
            'cohorte': context_ctx['cohorte'],
            'annee_choices': list(range(timezone.localdate().year - 5, timezone.localdate().year + 1)),
        }
        return render(request, self.template_name, context)


class ExportExcelView(StatisticienRequiredMixin, View):
    """Export Excel pour 2 rapports : depistage et cohorte."""

    def get(self, request, *args, **kwargs):
        rapport = self.kwargs.get('rapport')  # 'depistage' ou 'cohorte'
        annee = request.GET.get('annee') or str(timezone.localdate().year)
        trimestre = request.GET.get('trimestre') or ''
        mois = request.GET.get('mois') or ''
        unite = request.GET.get('unite') or ''
        if mois:
            trimestre = ''
        debut, fin = periode_range(annee, trimestre if trimestre else None, mois if mois else None)
        ctx = build_dashboard_context(debut, fin, unite if unite else None)

        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        except ImportError:
            return HttpResponse("openpyxl non installé", status=500)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Rapport"

        # Styles
        title_font = Font(bold=True, size=14, color="1a6fb0")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="1a6fb0", end_color="1a6fb0", fill_type="solid")
        thin = Side(style="thin", color="dfe3e6")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center")
        left = Alignment(horizontal="left", vertical="center")

        # En-tête
        ws.merge_cells('A1:D1')
        titre = f"Rapport trimestriel - {'Dépistage' if rapport=='depistage' else 'Résultats de traitement (cohorte)'}"
        ws['A1'] = titre
        ws['A1'].font = title_font
        ws['A1'].alignment = center

        ws.merge_cells('A2:D2')
        ws['A2'] = f"Période: {debut.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')} | Unité: {unite or 'Toutes'} | Généré le {timezone.localdate().strftime('%d/%m/%Y')}"
        ws['A2'].alignment = center
        ws['A2'].font = Font(italic=True, size=9, color="5f6368")

        row = 4
        if rapport == 'depistage':
            headers = ["Indicateur", "Valeur", "Numérateur", "Dénominateur / Note"]
            ws.append([])  # ensure row
            for col, h in enumerate(headers, 1):
                c = ws.cell(row=row, column=col, value=h)
                c.font = header_font
                c.fill = header_fill
                c.alignment = center
                c.border = border
            ws.column_dimensions['A'].width = 45
            ws.column_dimensions['B'].width = 18
            ws.column_dimensions['C'].width = 18
            ws.column_dimensions['D'].width = 30
            row += 1
            ep = ctx['epi']
            labo = ctx['labo']
            commu = ctx['commu']
            risque = ctx['risque']
            lignes = [
                ("Nombre de suspects TB", ep['nb_suspects'], ep['nb_suspects'], "Patients testes"),
                ("Taux de positivite (%)", ep['taux_positivite'], ep['nb_suspects'], "%"),
                ("Nouveaux cas TPM+", ep['nb_nouveaux_tpm_plus'], ep['nb_nouveaux_tpm_plus'], ""),
                ("Nouveaux cas TPM-", ep['nb_nouveaux_tpm_moins'], ep['nb_nouveaux_tpm_moins'], ""),
                ("Cas retraitement (Rechute)", ep['nb_retraitement'], ep['nb_retraitement'], ""),
                ("Taux notification /100k", "N/A", "", "Population non modelisee"),
                ("Frottis diagnostic", labo['nb_frottis_diag'], labo['nb_frottis_diag'], "2 lames / suspect"),
                ("Frottis controle (C2/C5/FIN)", labo['nb_frottis_controle'], labo['nb_frottis_controle'], ""),
                ("Taux conversion C2 (%)", labo['taux_conversion_c2'], "", ""),
                ("Cultures / DST", labo['nb_cultures_dst'], labo['nb_cultures_dst'], ""),
                ("DOTS communautaire (J)", commu['nb_dots_communautaire'], commu['nb_dots_communautaire'], "Fleche fiche"),
                ("Taux succes ASC (%)", commu['taux_succes_asc'], "", ""),
                ("TB pediatrique (<15 ans)", risque['nb_pediatrique'], risque['nb_pediatrique'], f"{risque['taux_pediatrique']}%"),
            ]
            for ind, val, num, denom in lignes:
                ws.cell(row=row, column=1, value=ind).alignment = left
                ws.cell(row=row, column=1).border = border
                ws.cell(row=row, column=2, value=val if val is not None else "N/A").alignment = center
                ws.cell(row=row, column=2).border = border
                ws.cell(row=row, column=3, value=num).alignment = center
                ws.cell(row=row, column=3).border = border
                ws.cell(row=row, column=4, value=denom).alignment = center
                ws.cell(row=row, column=4).border = border
                row += 1
            # placeholders
            row += 1
            ws.cell(row=row, column=1, value="Indicateurs non modélisés (N/A) : VIH/CTX/ARV, Rupture stock, CQ, Prison, Contacts, INH <5 ans").font = Font(italic=True, size=9, color="b06000")
        else:  # cohorte
            headers = ["Issue", "Effectif", "Taux (%)", "Cible OMS"]
            for col, h in enumerate(headers, 1):
                c = ws.cell(row=row, column=col, value=h)
                c.font = header_font
                c.fill = header_fill
                c.alignment = center
                c.border = border
            ws.column_dimensions['A'].width = 30
            ws.column_dimensions['B'].width = 18
            ws.column_dimensions['C'].width = 18
            ws.column_dimensions['D'].width = 22
            row += 1
            coh = ctx['cohorte']
            total = coh['total'] or 1
            lignes = [
                ("Total cohorte", coh['total'], "—", ""),
                ("Guéris", coh['gueris'], coh['taux_guerison'], ""),
                ("Traitement terminé", coh['termines'], round((coh['termines']/total*100),1) if coh['total'] else 0, ""),
                ("Succès (Guéri+Terminé)", coh['gueris']+coh['termines'], coh['taux_succes'], "≥90%"),
                ("Échec", coh['echecs'], coh['taux_echec'], "<5%"),
                ("Perdus de vue", coh['pdv'], coh['taux_abandon'], ""),
                ("Décédés", coh['decedes'], coh['taux_deces'], "<5%"),
                ("Transférés", coh['transferes'], round((coh['transferes']/total*100),1) if coh['total'] else 0, ""),
            ]
            for ind, eff, taux, cible in lignes:
                ws.cell(row=row, column=1, value=ind).alignment = left
                ws.cell(row=row, column=1).border = border
                ws.cell(row=row, column=2, value=eff).alignment = center
                ws.cell(row=row, column=2).border = border
                ws.cell(row=row, column=3, value=taux if taux!="—" else "—").alignment = center
                ws.cell(row=row, column=3).border = border
                ws.cell(row=row, column=4, value=cible).alignment = center
                ws.cell(row=row, column=4).border = border
                row += 1

        # ajuster hauteur
        for r in ws.iter_rows(min_row=1, max_row=row):
            for c in r:
                c.border = c.border or border

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        filename = f"rapport_{rapport}_{debut}_{fin}.xlsx"
        resp = HttpResponse(out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class ExportPdfView(StatisticienRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        rapport = self.kwargs.get('rapport')
        annee = request.GET.get('annee') or str(timezone.localdate().year)
        trimestre = request.GET.get('trimestre') or ''
        mois = request.GET.get('mois') or ''
        unite = request.GET.get('unite') or ''
        if mois:
            trimestre = ''
        debut, fin = periode_range(annee, trimestre if trimestre else None, mois if mois else None)
        ctx = build_dashboard_context(debut, fin, unite if unite else None)

        # Try reportlab, fallback to HTML pdf-like
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
        except ImportError:
            # fallback: render HTML and let browser print
            html = f"<h1>Rapport {rapport}</h1><p>{debut} - {fin}</p><pre>{ctx}</pre>"
            return HttpResponse(html)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm,
                                title=f"Rapport {rapport}", author="HGR Makala")
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=14, leading=18, textColor=HexColor('#1a6fb0'), alignment=1, spaceAfter=6)
        h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=11, leading=14, textColor=HexColor('#1a6fb0'), spaceBefore=10, spaceAfter=6)
        normal = ParagraphStyle('normal', parent=styles['Normal'], fontSize=9, leading=12)
        small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.grey)
        story = []
        story.append(Paragraph(f"Rapport trimestriel – {'Dépistage' if rapport=='depistage' else 'Résultats de traitement (cohorte)'}", title_style))
        story.append(Paragraph(f"Période : {debut.strftime('%d/%m/%Y')} – {fin.strftime('%d/%m/%Y')} &nbsp;|&nbsp; Unité : {unite or 'Toutes'} &nbsp;|&nbsp; Édité le {timezone.localdate().strftime('%d/%m/%Y')} – HGR Makala", small))
        story.append(Spacer(1, 6))

        if rapport == 'depistage':
            story.append(Paragraph("Indicateurs épidémiologiques et laboratoire", h2))
            ep = ctx['epi']; labo = ctx['labo']; commu = ctx['commu']; risque = ctx['risque']
            data = [
                ["Indicateur", "Valeur", "Note"],
                ["Suspects TB", str(ep['nb_suspects']), "Patients testés"],
                ["Taux positivité (%)", str(ep['taux_positivite']), ""],
                ["Nouveaux TPM+", str(ep['nb_nouveaux_tpm_plus']), ""],
                ["Nouveaux TPM-", str(ep['nb_nouveaux_tpm_moins']), ""],
                ["Retraitement", str(ep['nb_retraitement']), ""],
                ["Taux notification /100k", "N/A", "Population non mod."],
                ["Frottis diagnostic", str(labo['nb_frottis_diag']), ""],
                ["Frottis contrôle", str(labo['nb_frottis_controle']), ""],
                ["Conversion C2 (%)", str(labo['taux_conversion_c2']), ""],
                ["Cultures/DST", str(labo['nb_cultures_dst']), ""],
                ["DOTS communautaire", str(commu['nb_dots_communautaire']), ""],
                ["TB pédiatrique", f"{risque['nb_pediatrique']} ({risque['taux_pediatrique']}%)", "<15 ans"],
            ]
            t = Table(data, colWidths=[70*mm, 30*mm, 55*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), HexColor('#1a6fb0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ALIGN', (1,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#dfe3e6')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f6f8f9')]),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1,6))
            story.append(Paragraph("N/A : VIH/CTX/ARV, Rupture stock, CQ, Prison, Contacts, INH &lt;5 ans – modèles non gérés (AGENT.md hors périmètre).", small))
        else:
            story.append(Paragraph("Cohorte trimestrielle – résultats de traitement", h2))
            coh = ctx['cohorte']
            data = [
                ["Issue", "Effectif", "Taux (%)", "Cible OMS"],
                ["Total cohorte", str(coh['total']), "—", ""],
                ["Guéris", str(coh['gueris']), str(coh['taux_guerison']), ""],
                ["Traitement terminé", str(coh['termines']), str(round((coh['termines']/(coh['total'] or 1)*100),1)), ""],
                ["Succès", str(coh['gueris']+coh['termines']), str(coh['taux_succes']), "≥90%"],
                ["Échec", str(coh['echecs']), str(coh['taux_echec']), "<5%"],
                ["Perdus de vue", str(coh['pdv']), str(coh['taux_abandon']), ""],
                ["Décédés", str(coh['decedes']), str(coh['taux_deces']), "<5%"],
                ["Transférés", str(coh['transferes']), str(round((coh['transferes']/(coh['total'] or 1)*100),1)), ""],
            ]
            t = Table(data, colWidths=[55*mm, 30*mm, 30*mm, 40*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), HexColor('#1a6fb0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ALIGN', (1,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#dfe3e6')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f6f8f9')]),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1,6))
            story.append(Paragraph("Cohorte = traitements dont date_debut dans la période filtrée. Succès = Guéris + Traitement terminé.", small))

        story.append(Spacer(1,10))
        story.append(Paragraph("HGR Makala – Programme TB – Document officiel", small))
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        filename = f"rapport_{rapport}_{debut}_{fin}.pdf"
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
