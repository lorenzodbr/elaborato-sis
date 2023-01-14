"""
Versione 2.0 basata sullo script di Zenaro Stefano

FSMD_OPTIMIZER:
ottimizza un file blif con il progetto finito.

Il programma copia il file originale per n_copies volte,
poi esegue l'ottimizzazione su queste copie.
A fine ottimizzazione vengono memorizzati
i file blif ottimizzati e viene rieseguita la ottimizzazione.

Questo processo continua per n_layer volte.

A fine programma la FSMD
con l'area minore viene salvata nel file
FSMD_ottimizzato.blif
"""

__author__ = "Di Berardino Lorenzo"
__version__ = "2023-01-14 2.0"

import os
import re
import shutil
import subprocess
import sys
import time

boold = False

starttime = int(time.time())                               # timestamp inizio programma
current_dir = os.path.dirname(os.path.realpath(__file__))  # cartella script attuale
fsm_dir = os.path.join(current_dir, "lib")                # cartella con FSMD
fsm_path = os.path.join(fsm_dir, "FSMD.blif")              # file FSMD da ottimizzare

n_layer = 10   # numero strati di ottimizzazione
n_copies = 10  # numero di copie ottimizzate per strato


def copyntimes(t_file, t_n, t_layer):
    """
    Copia il file t_file per t_n volte con il nome:
    <nome_file>_L<t_layer>_<i>.<estensione>

    Dove:
    * <nome_file> e' il nome del file t_file senza estensione,
    * <t_layer> indica in che strato di ottimizzazione si trova il file
    * <i> e' un numero che va da 1 a <t_n>+1
    * <estensione> e' la estensione del file t_file e delle sue copie

    :param str t_file: percorso file da copiare
    :param int t_n: numero di copie
    :param int t_layer: usato nel nome della copia per indicare strato di ottimizzazione
    """
    # recupera percorso, nome e estensione del file
    file_path = os.path.dirname(t_file)
    file_nameext = os.path.basename(t_file)
    file_name, file_ext = os.path.splitext(file_nameext)

    # per t_n volte (da 1 a t_n1+) copia il file
    for i in range(1, t_n+1):
        copy_path = os.path.join(file_path, file_name + "_L" + str(t_layer) + "_" + str(i) + file_ext)
        shutil.copyfile(t_file, copy_path)


def optimize(blif_file, test_directory, output, optimized_blif):
    """
    Esegue SIS importando lo script di ottimizzazione.

    :param str blif_file: percorso file da ottimizzare
    :param str test_directory: cartella in cui si trova il file e in cui verra' memorizzato script temporaneo
    :param str output: percorso del file output della simulazione
    :param str optimized_blif: percorso file blif_file ottimizzato
    """
    sis_script = os.path.join(test_directory, "exec_test.txt")

    optimizer_script = os.path.join(current_dir, "_optimizer_scripts", "optimize_fsmd.script")
    
    sis_simulation_script = "set sisout " + output + "\n" + \
                            "read_blif " + blif_file + "\n" + \
                            "source " + optimizer_script + "\n" + \
                            "write_blif " + optimized_blif + "\n" + \
                            "quit"
    try:
        # crea file con script per eseguire script di simulazione
        with open(sis_script, "w") as s:
            s.write(sis_simulation_script)
        
        # vai nella cartella dei test e esegui lo script che esegue lo script di simulazione
        sis_command = "(cd " + test_directory + "; sis -t pla -f exec_test.txt -x)"
        subprocess.Popen(sis_command, stdout=subprocess.PIPE, shell=True).communicate()  # Launch SIS subprocess
    except IOError:
        return -1
    return 0


def parse_output(output):
    """
    Legge il file in output e restituisce area e numero di gate.

    :param str output: percorso file output della simulazione
    :return float total_area: area del circuito ottimizzato
    :return float gate_count: numero di gate del circuito ottimizzato
    """
    stats = False
    str_nodes = "-1"
    str_latches = "-1"

    with open(output, "r") as fout:
        line = fout.readline()
        while line != "":
            if "sis>print_stats" in line:
                stats = True
            
            if stats and "nodes" in line:
                str_nodes = line.split("nodes=")[1].split("\t")[0]
                str_latches = line.split("latches=")[1].split("\t")[0]

            line = fout.readline()

    nodes = int(str_nodes)
    latches = int(str_latches)

    return nodes, latches


def log(t_text, t_file):
    """
    logs text. (with timestamp)

    :param str t_text: string with text to write to file and print
    :param IO t_file: Opened log file
    """
    t_file.write("[{}]".format(int(time.time())) + t_text + "\n")


def get_opt_stats(t_file):
    """
    Restituisce le statistiche della ultima FSMD ottimizzata.

    :param str t_file: percorso file statistiche da leggere
    :return (None, float) total_area: area della vecchia FSMD ottimizzata
    :return (None, float) gate_count: numero di gate della vecchia FSMD ottimizzata
    """
    stats = None
    nodes_count = None
    latches_count = None

    try:
        with open(t_file, "r") as fstats:
            # salta il primo record
            fstats.readline()
            stats = fstats.readline().strip()
    
    except FileNotFoundError:
        pass

    if stats:
        nodes_count = float(stats.split(",")[0])
        latches_count = float(stats.split(",")[1])
    
    return nodes_count, latches_count


def write_opt_stats(t_file, nodes, latches):
    """
    Scrive le statistiche della nuova FSMD ottimizzata.

    :param str t_file: percorso file statistiche da scrivere
    :param float area: area della FSMD
    :param float gates: numero di gate della FSMD
    """
    with open(t_file, "w") as fstats:
        fstats.write("nodes,latches\n")
        fstats.write("{},{}".format(nodes, latches))

def delete_temp_files(path_outputs, path_layers):
    """
    Cancella tutti i file temporanei dentro a path
    """

    shutil.rmtree(path_outputs)

    for file in os.listdir(path_layers):
        if re.match(r"FSMD_L\d+_\d+.blif", file) or file == "opt_stats.csv" or file == "exec_test.txt":
            os.remove(os.path.join(path_layers, file))

if __name__ == "__main__":

    best_fsm_nodes = None
    best_fsm = ""
    best_fsm_latches = None

    file_path = os.path.dirname(fsm_path)
    outputs_path = os.path.join(file_path, "outputs")

    file_nameext = os.path.basename(fsm_path)
    file_name, file_ext = os.path.splitext(file_nameext)

    current_best_fsm_stats_path = os.path.join(file_path, "opt_stats.csv")
    
    # crea la cartella degli output di ottimizzazione (se necessario)
    if not os.path.isdir(outputs_path):
        os.makedirs(outputs_path)

    with open("fsmd_optimizer_log.txt", "w") as flog:
        # layer 1 di ottimizzazione
        # copia per n_copies volte il file
        if boold:
            log("creo layer 1 di simulazione", flog)
        copyntimes(fsm_path, n_copies, 1)

        # layer di ottimizzazione
        for layer in range(1, n_layer+1):
            if boold:
                log("eseguo ottimizzazioni del layer {}".format(layer), flog)
            
            for i in range(1, n_copies+1):
                # percorso della copia da ottimizzare, dell'output di simulazione e del blif ottimizzato
                copy_path = os.path.join(file_path, file_name + "_L" + str(layer) + "_" + str(i) + file_ext)
                output_path = os.path.join(outputs_path, file_name + "_L" + str(layer) + "_" + str(i) + "_optimized_out.txt")
                opt_blif_path = os.path.join(file_path, file_name + "_L" + str(layer+1) + "_" + str(i) + file_ext)

                if boold:
                    log("file da ottimizzare: " + copy_path, flog)
                    log("output della ottimizzazione: " + output_path, flog)
                    log("file ottimizzato: " + opt_blif_path, flog)

                # esegui SIS e ottimizza il file blif
                if optimize(copy_path, file_path, output_path, opt_blif_path) == 0:
                    nodes, latches = parse_output(output_path)
                    if boold:
                        log("Statistiche della fsmd dopo l'ottimizzazione '{}':".format(file_name + "_L" + str(layer) + "_" + str(i)), flog)
                        log("* nodi: {}".format(nodes), flog)
                        log("* latches: {}".format(latches), flog)

                    # memorizza statistiche della miglior fsm e
                    # il suo percorso
                    if not best_fsm_nodes:
                        best_fsm_nodes = nodes
                        best_fsm_latches = latches
                        best_fsm = opt_blif_path

                    elif best_fsm_nodes > nodes:
                        best_fsm_nodes = nodes
                        best_fsm_latches = latches
                        best_fsm = opt_blif_path
                else:
                    log("[ERRORE] Qualcosa e' andato storto", flog)
                    sys.exit(1)
        
        log("La miglior fsmd e' '{}'".format(best_fsm), flog)
        log("* nodi: {}".format(best_fsm_nodes), flog)
        log("* latches: {}".format(best_fsm_latches), flog)
        log("L'ottimizzazione e' durata {} secondi".format(int(time.time()) - starttime), flog)

        current_best_fsm_nodes_count, current_best_fsm_latches_count = get_opt_stats(current_best_fsm_stats_path)

        if not current_best_fsm_nodes_count or not current_best_fsm_latches_count:
            # non e' stato possibile leggere statistiche della ottimizzazione migliore passata
            # copia la FSM migliore mettendoci un nome riconoscibile
            shutil.copy(best_fsm, os.path.join(file_path, "FSMD_ottimizzato.blif"))

            # memorizza le statistiche della FSM migliore
            write_opt_stats(current_best_fsm_stats_path, best_fsm_nodes, best_fsm_latches)
            print(1)

        elif current_best_fsm_nodes_count > best_fsm_nodes:
            # copia la FSM migliore mettendoci un nome riconoscibile
            shutil.copy(best_fsm, os.path.join(file_path, "FSMD_ottimizzato.blif"))

            # memorizza le statistiche della FSM migliore
            write_opt_stats(current_best_fsm_stats_path, best_fsm_nodes, best_fsm_latches)
            print(1)
        
        else:
            # la FSM ottimizzata e' peggiore o uguale alla migliore ottimizzazione registrata
            print(0)
    delete_temp_files(outputs_path, fsm_dir)
