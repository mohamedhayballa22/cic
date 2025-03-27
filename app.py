from flask import Flask, render_template, request
from datetime import datetime, date

app = Flask(__name__)

def format_decimal_fr(value, precision=2):
    """Formats a number with a comma decimal separator."""
    if value is None:
        return ""
    try:
        # Format with standard period first
        formatted_value = "{:.{prec}f}".format(float(value), prec=precision)
        # Replace period with comma
        return formatted_value.replace('.', ',')
    except (ValueError, TypeError):
        # Handle cases where value is not a number gracefully
        return value

# Register the custom filter with Jinja2
app.jinja_env.filters['decimal_fr'] = format_decimal_fr

# Données globales initialisées (Constants)
JOURS_OUVRES_TOTAL_2024 = 231
NB_BENEFICIAIRES = 3635
MASSE_SALARIALE_GLOBALE = 163_290_000  # €
ENVELOPPE_INTERESSEMENT = 12_900_000  # €
ANNEE_DEBUT_CALCUL = datetime.strptime("01/01/2024", "%d/%m/%Y")
ANNEE_FIN_CALCUL = datetime.strptime("31/12/2024", "%d/%m/%Y")
JOURS_ANNEE_CALCUL = (ANNEE_FIN_CALCUL - ANNEE_DEBUT_CALCUL).days + 1
NET_FACTOR = 0.908
DATE_LIMITE_ENTREE = datetime(2024, 9, 30)


def calculate_interessement(salaire_mensuel, absences_ouvrees, date_entree_str, date_sortie_str):
    """
    Calculates the interessement based on user inputs and global data.
    Returns a tuple: (results_dict, debug_info_dict)
    """
    try:
        # --- Data Preparation and Validation ---
        date_entree = datetime.strptime(date_entree_str, "%d/%m/%Y")
        date_sortie = datetime.strptime(date_sortie_str, "%d/%m/%Y")

        if date_entree.year != 2024:
            raise ValueError("La date d'entrée doit être en 2024")

        if date_entree > DATE_LIMITE_ENTREE:
            raise ValueError("Selon les règles définies, aucun intéressement n'est versé pour une date d'entrée dans l'entreprise postérieure au 30 Septembre 2024.")


        # --- Calculations ---

        # 1. Presence Calculation
        jours_presence_calendaire = (date_sortie - date_entree).days + 1
        ratio_presence_calendaire = jours_presence_calendaire / JOURS_ANNEE_CALCUL

        jours_ouvres_theoriques = JOURS_OUVRES_TOTAL_2024 * ratio_presence_calendaire
        jours_ouvres_reels = max(jours_ouvres_theoriques - absences_ouvrees, 0)
        # Ensure presence ratio isn't negative or artificially high if absences > theoretical days
        presence_ratio = jours_ouvres_reels / JOURS_OUVRES_TOTAL_2024
        presence_ratio = max(0, min(presence_ratio, 1)) # Clamp between 0 and 1

        # 2. Salary Calculation Base
        salaire_annuel_prorata = salaire_mensuel * 12 * ratio_presence_calendaire

        # --- Interessement Calculation ---
        part_presence_totale = 0.20 * ENVELOPPE_INTERESSEMENT

        part_presence_indiv = (part_presence_totale / NB_BENEFICIAIRES) * (jours_ouvres_reels / JOURS_OUVRES_TOTAL_2024)


        part_salaire_totale = 0.80 * ENVELOPPE_INTERESSEMENT
        part_salaire_indiv = (salaire_annuel_prorata / MASSE_SALARIALE_GLOBALE) * part_salaire_totale

        interessement_brut = part_presence_indiv + part_salaire_indiv # Using the revised presence part

        # Net calculation - Apply CSG/CRDS (check specific rules, this is a common approximation)
        interessement_net = interessement_brut * 0.908

        results = {
            "Estimation brute (€)": round(interessement_brut, 2),
            "Estimation nette (€)": round(interessement_net, 2),
        }

        debug_info = {
            "ratio_presence_calendaire": ratio_presence_calendaire,
            "presence_ratio": presence_ratio, # Ratio jours ouvrés réels / total jours ouvrés année
            "salaire_annuel": salaire_annuel_prorata
        }

        return results, debug_info, None # No error

    except ValueError as ve:
        # Handle date parsing errors or logical errors like entry > exit
        return None, None, ve
    except Exception as e:
        # Handle other potential errors (e.g., calculation issues)
        # Log the error
        return None, None, f"Une erreur inattendue est survenue lors du calcul: {e}"


@app.route('/')
def index():
    # Pass current year to base template for footer
    return render_template('index.html', now=date.today())

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        # --- Get User Input ---
        salaire_mensuel = float(request.form['salaire_mensuel'])
        absences_ouvrees = int(request.form['absences_ouvrees'])
        entered_in_2024 = request.form.get('entered_in_2024')
        date_sortie_str = "31/12/2024"

        if entered_in_2024 == 'yes':
            date_entree_str = request.form['date_entree_str']
            if not date_entree_str:
                 # Handle case where 'yes' is checked but date is empty
                 return render_template('index.html', error="Veuillez fournir la date d'entrée.", now=date.today())
        else:
            date_entree_str = "01/01/2024"

        # --- Perform Calculation ---
        results, debug_info, error = calculate_interessement(
            salaire_mensuel,
            absences_ouvrees,
            date_entree_str,
            date_sortie_str
        )

        # --- Display Results or Error ---
        if error:
            # Redisplay form with error message and previous inputs
            return render_template('index.html', error=error, now=date.today())
        else:
            # Store inputs to display them on the results page for clarity
            user_inputs = {
                'salaire_mensuel': salaire_mensuel,
                'absences_ouvrees': absences_ouvrees,
                'date_entree_str': date_entree_str,
                'date_sortie_str': date_sortie_str,
                'entered_in_2024': entered_in_2024
            }
            return render_template('result.html', results=results, inputs=user_inputs, debug_info=debug_info, now=date.today())

    except ValueError:
        # Handle cases where conversion to float/int fails
        return render_template('index.html', error="Veuillez entrer des valeurs numériques valides pour le salaire et les absences.", now=date.today())
    except Exception as e:
        # Catch any other unexpected errors during form processing
        app.logger.error(f"Form processing error: {e}") # Log the error
        return render_template('index.html', error=f"Une erreur inattendue est survenue: {e}", now=date.today())


@app.context_processor
def inject_now():
    return {'now': date.today()}