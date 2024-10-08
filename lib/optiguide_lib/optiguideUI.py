import sys
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QMessageBox, QDialog, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd
from paretoset import paretoset
import matplotlib.pyplot as plt
import mplcursors
from functools import partial
import os

# import matplotlib.pyplot as plt
# print(plt.style.available)

# new dir, dir0, dir1
dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")) + "/"
dir0 = dir + "lib/optiguide_lib/"
dir1 = dir + "procurementDgProject/"
# dir="/Users/talmanie/Desktop/OptiGuide/procurementDgProject/"
# dir0="/Users/talmanie/Desktop/OptiGuide/lib/optiguide_lib/"
# original dir
#dir="/Users/talmanie/Desktop/OptiGuide/config_procurement/"
#dir="/Users/talmanie/Desktop/OptiGuide/config_optiSensor/"
f = open(dir0+"paretoDB.json","r")
paretoDB = json.loads(f.read())

# Extract required data from config json
# original objs
# f = open(dir+"config.json", "r")
# config = json.loads(f.read())
# confObjs = config["objs"]

# new confObjs from reqSpec and initialObj from config
with open(dir1+"config.json", "r") as f:
    config = json.load(f)
with open(dir+config["reqSpec"],"r") as f:
    reqSpec = json.load(f)
confObjs = reqSpec["objectives"]["schema"]
initialObj = config["initialObj"]

# System Global Variables
systemState = list()
bestSoFar = list()
#-------------------------------------------------------------------------------
# Prepare Pareto optimal graph from the ParetoDB points based on the selected x_axis & y_axis objectives and the current weights.
def paretoOptimal(paretoDB, cObjs, x_axis , y_axis, currentWeights):

    # compute the current utility for each point in paretoDB:
    currentUtility=list()
    for p in paretoDB:
        currentUtility.append(round(sum([ p["norm_objectives"][obj] * currentWeights[obj] for obj in p["norm_objectives"] ]),3))

    if x_axis=="utility":
        graph_points=pd.DataFrame({
                    x_axis: currentUtility,
                    y_axis: [p["objectives"][y_axis] for p in paretoDB]
                    })
        mask = paretoset(graph_points, sense=["max", cObjs[y_axis]["minMax"]])
    else:
        graph_points=pd.DataFrame({
                x_axis: [p["objectives"][x_axis] for p in paretoDB],
                y_axis: [p["objectives"][y_axis] for p in paretoDB]
                })
        mask = paretoset(graph_points, sense=[cObjs[x_axis]["minMax"], cObjs[y_axis]["minMax"]])

    # Filter out the set of non-dominated solutions from the set of feasible solutions
    paretoGraph_points = graph_points[mask]
    #print(graph_points)
    #print(paretoGraph_points)

    # Display the feasible solution points
    graph_points.plot(kind = "scatter", x = x_axis, y = y_axis, title = "Feasible Solutions")
    #plt.show()

    # Display the Pareto curve of non-dominated solutions
    paretoGraph_points.plot(kind = "scatter", x = x_axis, y = y_axis, title = "Pareto Solutions")
    #plt.show()

    # Get the index of each Pareto graph point
    paretoIndices=[paretoGraph_points.index[point] for point in range(len(paretoGraph_points))]
    #print(paretoIndices)

    # Retrieve the related data for each Pareto graph point from ParetoDB
    paretoTable_points=[]
    for index in paretoIndices:
        paretoTable_points.append({
            "index": index,
            "utility": currentUtility[index],
            "weights": paretoDB[index]["weights"],
            "input": paretoDB[index]["input"],
            "output": paretoDB[index]["output"],
            "objectives": paretoDB[index]["objectives"],
            "norm_objectives": paretoDB[index]["norm_objectives"]
            })
    #print(paretoTable_points)

    # Sort the list of table points based on the x-axis key values
    if x_axis=="utility":
        paretoTable_points = sorted(paretoTable_points, key=lambda x: x["utility"])
    else:
        paretoTable_points = sorted(paretoTable_points, key=lambda x: x["objectives"][x_axis])

    paretoFront_data={ "currentWeights": currentWeights, "paretoGraph": paretoGraph_points, "paretoTable": paretoTable_points}

    return paretoFront_data
#-------------------------------------------------------------------------------
class ParetoFrontGUI(QMainWindow):

    def __init__(self, paretoFront_data):
        super(ParetoFrontGUI, self).__init__()
        self.setWindowTitle("Current Trade-off")
        self.setGeometry(300, 100, 800, 720)
        self.paretoFront_data = paretoFront_data
        self.setup_ui()
#-------------------------------------------------------------------------------
    def setup_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create figure and canvas and Navigation toolbar for Pareto front plot
        # plt.style.use('seaborn')   # Matplotlib pre-defined style
        plt.style.use('seaborn-v0_8')
        figure = Figure()
        self.canvas = FigureCanvas(figure)
        layout.addWidget(self.canvas)
        self.plot = figure.add_subplot(111)
        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setIconSize(QSize(20, 20))
        layout.addWidget(toolbar)
        # Plot Pareto front with initial data
        self.update_graph()

        # Create QLabel for weights of current utility
        self.currentWeights_label = QLabel()
        self.currentWeights_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.currentWeights_label)
        # Add the initial Utility weights to the label
        self.update_weightsLabel()

        # Create table widget for Pareto front data
        self.table = QTableWidget()
        layout.addWidget(self.table)
        # Populate table with Pareto initial data
        self.update_table()

#-------------------------------------------------------------------------------
    def update_graph(self):
        xAxis = self.paretoFront_data["paretoGraph"].iloc[:, 0]
        yAxis = self.paretoFront_data["paretoGraph"].iloc[:, 1]
        scatter = self.plot.scatter(xAxis, yAxis)
        self.plot.set_xlabel(self.paretoFront_data["paretoGraph"].columns[0], weight='bold')
        self.plot.set_ylabel(self.paretoFront_data["paretoGraph"].columns[1], weight='bold')
        self.plot.grid(True)

        # Use mplcursors to display coordinates on hover over graph points
        mplcursors.cursor(scatter,hover=True).connect("add", lambda sel: sel.annotation.set_text(f"({sel.target[0]}, {sel.target[1]})"))
        self.canvas.draw()
#-------------------------------------------------------------------------------
    def update_weightsLabel(self):
        currentWeights_text = ',  '.join(f'<b>{obj}</b>: {round(self.paretoFront_data["currentWeights"][obj],3)}' for obj in self.paretoFront_data["currentWeights"])
        self.currentWeights_label.setText("<b style='color:#4C72B0;'> Weights of Current Utility: </b>" + currentWeights_text)
#-------------------------------------------------------------------------------
    def update_table(self):
        self.table.setRowCount(len(self.paretoFront_data["paretoTable"]))
        self.table.setVerticalHeaderLabels(["Rec {}".format(point+1) for point in range(len(self.paretoFront_data["paretoTable"]))])
        self.table.setColumnCount(len(confObjs)+3)  # 3 additional columns for : utility, solution, choose?
        self.table.setHorizontalHeaderLabels(["utility"]+[ obj for obj in confObjs]+["solution"]+["Choose?"])

        # Populate table with utility values
        for point in range(len(self.paretoFront_data["paretoTable"])):
            item = QTableWidgetItem(str(round(self.paretoFront_data["paretoTable"][point]["utility"], 3)))
            item.setTextAlignment(Qt.AlignCenter)  # Center text alignment
            self.table.setItem(point, 0, item)

        # Populate table with objective values
        for point in range(len(self.paretoFront_data["paretoTable"])):
            for i, obj in enumerate(confObjs):
                item = QTableWidgetItem(str(self.paretoFront_data["paretoTable"][point]["objectives"][obj]))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(point, i+1, item)

        # create a QFont object for underlining
        fontU = QFont()
        fontU.setUnderline(True)  # set underline

        # Populate table with solution values
        for point in range(len(self.paretoFront_data["paretoTable"])):
            item = QTableWidgetItem("Click for details")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFont(fontU)
            item.setData(Qt.UserRole, self.paretoFront_data["paretoTable"][point]["output"])
            self.table.setItem(point, self.table.columnCount()-2, item)
        # connect the cellClicked signal to the show_dict slot
        self.table.cellClicked.connect(self.show_dict)

        # Add "Best" buttons to the last column of each row
        for row in range(self.table.rowCount()):
            button = QPushButton("Best")
            button.setStyleSheet("background-color: lightgray; color: black;")
            self.table.setCellWidget(row, self.table.columnCount()-1, button)
            # When a button is clicked, call the button_clicked function with the index of row containing the clicked button
            button.clicked.connect(partial(self.button_clicked, row_index=row))

        # Formatting : Set horizontal and vertical header labels in bold
        fontB = QFont()
        fontB.setBold(True)
        for i in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(i).setFont(fontB)
        for i in range(self.table.rowCount()):
            self.table.verticalHeaderItem(i).setFont(fontB)
        # Resize the columns to fit the contents
        self.table.resizeColumnsToContents()
#-------------------------------------------------------------------------------
    def show_dict(self, row, col):
        # check if the clicked cell is the one containing dictionary
        if col == self.table.columnCount()-2:
            item = self.table.item(row, col)
            dictionary = item.data(Qt.UserRole)

            # create a dialog
            dialog = QDialog(self)
            layout = QVBoxLayout(dialog)
            dialog.setWindowTitle("Solution Details for Rec "+f'{row+1}')
            # Set fixed size for QDialog
            dialog.setFixedSize(400, 300)

            # create a tree widget
            tree = QTreeWidget()
            layout.addWidget(tree)
            tree.setHeaderLabels(["Item", "value"])
            # Set minimum size for tree widget
            tree.setMinimumSize(300, 200)

            # Set initial column widths
            tree.setColumnWidth(0, 150)
            tree.setColumnWidth(1, 300)

            # Set the horizontal scroll bar
            tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            # recursive function to add dictionary to tree widget
            def add_dict_to_tree(parent_item, dictionary):
                for key, value in dictionary.items():
                    child = QTreeWidgetItem(parent_item)
                    child.setText(0, str(key))
                    if isinstance(value, dict):
                        add_dict_to_tree(child, value)
                    else:
                        child.setText(1, str(value))

            # add dictionary to tree widget
            add_dict_to_tree(tree.invisibleRootItem(), dictionary)

            dialog.exec_()
#-------------------------------------------------------------------------------
    def button_clicked(self, row_index):
        # Perform actions based on row index of the clicked button
        currentWeights = self.paretoFront_data["paretoTable"][row_index]["weights"]
        currentXaxis= self.paretoFront_data["paretoGraph"].columns[0]
        currentYaxis= self.paretoFront_data["paretoGraph"].columns[1]

        # Ask user for confirmation
        reply = QMessageBox.question(self, 'Confirmation', 'Are you sure this selection is the best?', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            bestSoFar.append(self.paretoFront_data["paretoTable"][row_index])   # compute its updated utility on the fly
            #print(bestSoFar)
            paretoFront_newData = paretoOptimal(paretoDB, confObjs, currentXaxis, currentYaxis, currentWeights)
            self.update_state(paretoFront_newData)
#-------------------------------------------------------------------------------
    def update_state(self, paretoFront_newData):

        self.paretoFront_data=paretoFront_newData
        systemState.append(paretoFront_newData)

        # update Pareto graph
        self.plot.clear() # clear the old plot
        self.update_graph()

        # update Current Weights label
        self.update_weightsLabel()

        # update Pareto Table
        self.table.clear() # clear the old table
        self.update_table()
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    # Initialization
    currentWeights =  { obj: 1/len(confObjs) for obj in confObjs}
    #currentWeights =  {'cost': 0.923860397184827, 'co2': 0.20285975728920072, 'manufTime': 0.32454565994026213}
    paretoFront_data = paretoOptimal(paretoDB, confObjs,"utility", config["initialObj"], currentWeights)
    #paretoFront_data = paretoOptimal(paretoDB, confObjs,"aggr_coverage", "cost", currentWeights)
    #paretoFront_data = paretoOptimal(paretoDB, confObjs,"cost", "co2", currentWeights)
    systemState.append(paretoFront_data)


    # Create Qt application
    app = QApplication(sys.argv)

    # Create main window and show
    main_window = ParetoFrontGUI(paretoFront_data)
    main_window.show()

    # Start event loop
    sys.exit(app.exec_())
#-------------------------------------------------------------------------------
