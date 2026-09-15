import io
import json
from datetime import date, datetime, timedelta
from calendar import month_name

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import View

from apps.patients.models import EpisodeTB, IssueFinale, Patient, StatutEpisodeTB, StatutDossier, TypePatient, SiteMaladie, Sexe
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
        rapport = self.kwargs.get('rapport')
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

        title_font = Font(bold=True, size=14, color="1a6fb0")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="1a6fb0", end_color="1a6fb0", fill_type="solid")
        thin = Side(style="thin", color="dfe3e6")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center")
        left = Alignment(horizontal="left", vertical="center")

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
            ws.append([])
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
            row += 1
            ws.cell(row=row, column=1, value="Indicateurs non modélisés (N/A) : VIH/CTX/ARV, Rupture stock, CQ, Prison, Contacts, INH <5 ans").font = Font(italic=True, size=9, color="b06000")
        else:
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

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
        except ImportError:
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
            story.append(Paragraph("N/A : VIH/CTX/ARV, Rupture stock, CQ, Prison, Contacts, INH &lt;5 ans – modèles non gérés.", small))
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


class TableauBordView(StatisticienRequiredMixin, View):
    """Tableau de bord principal pour l'agent statistique."""
    template_name = 'statistics/tableau_bord.html'

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()

        tous = EpisodeTB.objects.all()

        cas_actifs = tous.filter(
            statut__in=[StatutEpisodeTB.PROVISOIRE, StatutEpisodeTB.CONFIRME, StatutEpisodeTB.EN_TRAITEMENT]
        ).count()

        guerisons = tous.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='GUERI').count()
        echecs = tous.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='ECHEC').count()
        abandons = tous.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='PERDU_DE_VUE').count()
        nouveaux = tous.filter(type_patient=TypePatient.NOUVEAU).count()
        rechutes = tous.filter(type_patient=TypePatient.RECHUTE).count()
        transferes = tous.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='TRANSFERE').count()
        deces = tous.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='DECEDE').count()

        total_episodes = tous.count() or 1

        mois_labels = []
        mois_nouveaux = []
        mois_rechutes = []
        mois_abandons = []
        mois_deces = []
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            debut = date(y, m, 1)
            if m == 12:
                fin = date(y + 1, 1, 1) - timedelta(days=1)
            else:
                fin = date(y, m + 1, 1) - timedelta(days=1)
            base = tous.filter(date_ouverture__gte=debut, date_ouverture__lte=fin)
            mois_labels.append(month_name[m][:3])
            mois_nouveaux.append(base.filter(type_patient=TypePatient.NOUVEAU).count())
            mois_rechutes.append(base.filter(type_patient=TypePatient.RECHUTE).count())
            mois_abandons.append(base.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='PERDU_DE_VUE').count())
            mois_deces.append(base.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='DECEDE').count())

        type_labels = []
        type_data = []
        for code, label in TypePatient.choices:
            if code == TypePatient.REPRISE_ABANDON:
                continue
            count = tous.filter(type_patient=code).count()
            type_labels.append(label)
            type_data.append(count)

        sexe_labels = []
        sexe_data = []
        sexe_colors = ['#375a83', '#e74c3c']
        for code, label in Sexe.choices:
            count = Patient.objects.filter(sexe=code).count()
            sexe_labels.append(label)
            sexe_data.append(count)

        derniers = (
            EpisodeTB.objects
            .select_related('patient')
            .order_by('-cree_le')[:5]
        )

        context = {
            'active_nav': 'statistics_tableau_bord',
            'today': today,
            'cas_actifs': cas_actifs,
            'guerisons': guerisons,
            'echecs': echecs,
            'abandons': abandons,
            'nouveaux': nouveaux,
            'rechutes': rechutes,
            'transferes': transferes,
            'deces': deces,
            'total_episodes': total_episodes or 1,
            'mois_labels': json.dumps(mois_labels),
            'mois_nouveaux': json.dumps(mois_nouveaux),
            'mois_rechutes': json.dumps(mois_rechutes),
            'mois_abandons': json.dumps(mois_abandons),
            'mois_deces': json.dumps(mois_deces),
            'type_labels': json.dumps(type_labels),
            'type_data': json.dumps(type_data),
            'sexe_labels': json.dumps(sexe_labels),
            'sexe_data': json.dumps(sexe_data),
            'sexe_colors': json.dumps(sexe_colors),
            'derniers': derniers,
        }
        return render(request, self.template_name, context)


# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────

RAPPORTS = [
    {
        'id': 'nouveaux',
        'titre': 'Liste des nouveaux cas enregistrés',
        'icone': 'file alternate outline',
        'indicateur_label': 'cas enregistrés',
    },
    {
        'id': 'en_cours',
        'titre': 'Liste des cas en cours de traitement',
        'icone': 'clipboard list',
        'indicateur_label': 'cas actifs',
    },
    {
        'id': 'cohorte',
        'titre': 'Rapport des résultats de traitement (cohorte)',
        'icone': 'chart pie',
        'indicateur_label': 'de succès thérapeutique',
        'indicateur_pct': True,
    },
    {
        'id': 'abandons',
        'titre': "Liste des abandons thérapeutiques",
        'icone': 'remove circle outline',
        'indicateur_label': 'abandons',
    },
    {
        'id': 'rechutes',
        'titre': 'Liste des cas de rechute',
        'icone': 'redo',
        'indicateur_label': 'rechutes',
    },
]


def _get_periode_filters(request):
    """Parse les filtres de période depuis la requête.

    Retourne (annee, type_filter, valeur, date_debut, date_fin, debut, fin, periode_label)
    """
    type_filter = request.GET.get('type_filter') or ''
    annee = request.GET.get('annee') or str(timezone.localdate().year)
    valeur = request.GET.get('valeur') or ''
    date_debut_str = request.GET.get('date_debut') or ''
    date_fin_str = request.GET.get('date_fin') or ''

    date_debut = None
    date_fin = None
    if date_debut_str and date_fin_str:
        try:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    mois = ''
    trimestre = ''
    semestre = ''

    if type_filter == 'mensuel' and valeur:
        mois = valeur
    elif type_filter == 'trimestrielle' and valeur:
        trimestre = valeur
    elif type_filter == 'semestrielle' and valeur:
        semestre = valeur

    debut, fin = periode_range(
        annee,
        trimestre=trimestre or None,
        mois=mois or None,
        semestre=semestre or None,
        date_debut=date_debut,
        date_fin=date_fin,
    )

    periode_label = ''
    if date_debut and date_fin:
        periode_label = f"{date_debut.strftime('%d/%m/%Y')} – {date_fin.strftime('%d/%m/%Y')}"
    elif type_filter == 'semestrielle' and valeur:
        periode_label = f"Semestre {valeur} {annee}"
    elif type_filter == 'trimestrielle' and valeur:
        periode_label = f"Trimestre {valeur} {annee}"
    elif type_filter == 'mensuel' and valeur:
        noms_mois = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        periode_label = f"{noms_mois[int(valeur)]} {annee}"
    else:
        periode_label = f"Année {annee}"

    return annee, type_filter, valeur, date_debut, date_fin, debut, fin, periode_label


def _rapport_queryset(rapport_id, debut, fin):
    qs = EpisodeTB.objects.filter(date_ouverture__gte=debut, date_ouverture__lte=fin)
    if rapport_id == 'nouveaux':
        qs = qs.filter(type_patient=TypePatient.NOUVEAU)
    elif rapport_id == 'en_cours':
        qs = qs.filter(statut__in=[StatutEpisodeTB.PROVISOIRE, StatutEpisodeTB.CONFIRME, StatutEpisodeTB.EN_TRAITEMENT])
    elif rapport_id == 'cohorte':
        qs = qs.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final__in=['GUERI', 'TERMINE', 'ECHEC', 'PERDU_DE_VUE', 'DECEDE', 'TRANSFERE'])
    elif rapport_id == 'abandons':
        qs = qs.filter(statut=StatutEpisodeTB.CLOTURE, resultat_final='PERDU_DE_VUE')
    elif rapport_id == 'rechutes':
        qs = qs.filter(type_patient=TypePatient.RECHUTE)
    return qs.select_related('patient')


def _build_rapport_indicateur(rapport_id, qs):
    count = qs.count()
    if rapport_id == 'cohorte':
        total = qs.count() or 1
        succes = qs.filter(resultat_final__in=['GUERI', 'TERMINE']).count()
        return round(succes / total * 100), '%'
    return count, ''


class ReportingView(StatisticienRequiredMixin, View):
    template_name = 'statistics/reporting.html'

    def get(self, request, *args, **kwargs):
        annee, type_filter, valeur, date_debut, date_fin, debut, fin, periode_label = _get_periode_filters(request)

        rapports_data = []
        for r in RAPPORTS:
            qs = _rapport_queryset(r['id'], debut, fin)
            iv, suffixe = _build_rapport_indicateur(r['id'], qs)
            rapports_data.append({
                **r,
                'valeur': iv,
                'suffixe': suffixe,
            })

        context = {
            'active_nav': 'statistics_reporting',
            'annee': annee,
            'type_filter': type_filter,
            'valeur': valeur,
            'date_debut': date_debut.strftime('%Y-%m-%d') if date_debut else '',
            'date_fin': date_fin.strftime('%Y-%m-%d') if date_fin else '',
            'debut': debut,
            'fin': fin,
            'rapports': rapports_data,
            'periode_label': periode_label,
            'annee_choices': list(range(timezone.localdate().year - 5, timezone.localdate().year + 1)),
        }

        if request.headers.get('HX-Request'):
            return render(request, 'statistics/reporting_rapports.html', context)

        return render(request, self.template_name, context)


class RapportDetailView(StatisticienRequiredMixin, View):
    """Page dediee au détail d'un rapport."""
    template_name = 'statistics/rapport_detail.html'
    PER_PAGE = 15

    def get(self, request, *args, **kwargs):
        from django.core.paginator import Paginator, EmptyPage

        rapport_id = kwargs.get('rapport_id')
        rapport_info = next((r for r in RAPPORTS if r['id'] == rapport_id), None)
        if not rapport_info:
            return HttpResponse('Rapport introuvable', status=404)

        annee, type_filter, valeur, date_debut, date_fin, debut, fin, periode_label = _get_periode_filters(request)
        qs = _rapport_queryset(rapport_id, debut, fin)
        iv, suffixe = _build_rapport_indicateur(rapport_id, qs)
        total = qs.count()

        paginator = Paginator(qs, self.PER_PAGE)
        page_number = int(request.GET.get('page') or 1)
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        page_range = []
        cur = page_obj.number
        for num in paginator.page_range:
            if num == cur or (num >= cur - 2 and num <= cur + 2):
                page_range.append(num)

        context = {
            'rapport': rapport_info,
            'items': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'page_range': page_range,
            'valeur': iv,
            'suffixe': suffixe,
            'periode_label': periode_label,
            'total': total,
            'rapport_id': rapport_id,
            'annee': annee,
            'type_filter': type_filter,
            'valeur_filter': valeur,
            'date_debut': date_debut.strftime('%Y-%m-%d') if date_debut else '',
            'date_fin': date_fin.strftime('%Y-%m-%d') if date_fin else '',
            'active_nav': 'statistics_reporting',
        }

        return render(request, self.template_name, context)
