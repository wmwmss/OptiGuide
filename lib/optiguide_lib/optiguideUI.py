import sys
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QMessageBox, QDialog, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QRadioButton, QComboBox
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd
from paretoset import paretoset
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
import mplcursors
from functools import partial
import seaborn as sns
import numpy as np
import os
#import warnings
#warnings.filterwarnings("ignore", module="mplcursors._pick_info")
#-------------------------------------------------------------------------------

# Get the absolute path to a resource
def resource_path(relative_path):
    try:
        # Packaged environment
        base_path = sys._MEIPASS
    except AttributeError:
        # Development environment
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    return os.path.join(base_path, relative_path)

#-------------------------------------------------------------------------------

# extract initialObj from config
config_path = resource_path("procurementDgProject/config.json")
with open(config_path, "r") as f:
    config = json.load(f)
initialObj = config["settings"]["initialObj"]

# extract objsSchema from reqSpec
reqSpec_path = resource_path(config["reqSpec"])
with open(reqSpec_path, "r") as f:
    reqSpec = json.load(f)
objsSchema = reqSpec["objectives"]["schema"]

# extract ParetoOptimal Database
paretoDB_path = resource_path("lib/optiguide_lib/paretoDB.json")
with open(paretoDB_path, "r") as f:
    paretoDB = json.load(f)

# System Global Variables
systemState = list()
currentTable = list()
bestSoFar = list()
optimalRec = {}
#-------------------------------------------------------------------------------
# Prepare Pareto optimal graph from the ParetoDB points based on the selected x_axis & y_axis objectives and the current weights.
def paretoOptimal(paretoDB, objsSchema, x_axis , y_axis, currentWeights):

    # compute the current utility for each point in paretoDB:
    currentUtility=list()
    for p in paretoDB:
        currentUtility.append(round(sum([ p["norm_objectives"][obj] * currentWeights[obj] for obj in p["norm_objectives"] ])/ sum([currentWeights[obj] for obj in p["norm_objectives"]]),3))

    if x_axis=="utility":
        graph_points=pd.DataFrame({
                    x_axis: currentUtility,
                    y_axis: [p["objectives"][y_axis] for p in paretoDB]
                    })
        mask = paretoset(graph_points, sense=["max", objsSchema[y_axis]["minMax"]])
    else:
        graph_points=pd.DataFrame({
                x_axis: [p["objectives"][x_axis] for p in paretoDB],
                y_axis: [p["objectives"][y_axis] for p in paretoDB]
                })
        mask = paretoset(graph_points, sense=[objsSchema[x_axis]["minMax"], objsSchema[y_axis]["minMax"]])

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

    # Retrieve the related data for each Pareto graph point from ParetoDB using the original paretoDB index
    paretoTable_points=[]
    for index in paretoIndices:
        paretoTable_points.append({
            "index": index,
            "utility": currentUtility[index],
            "precomputed_utility": paretoDB[index]["utility"],
            "weights": paretoDB[index]["weights"],
            "input": paretoDB[index]["input"],
            "output": paretoDB[index]["output"],
            "objectives": paretoDB[index]["objectives"],
            "norm_objectives": paretoDB[index]["norm_objectives"]
            })
    #print(paretoTable_points)

    # Sort the list of table points based on the x-axis key values
    #if x_axis=="utility":
    #    paretoTable_points = sorted(paretoTable_points, key=lambda x: x["utility"])
    #else:
    #    paretoTable_points = sorted(paretoTable_points, key=lambda x: x["objectives"][x_axis])

    paretoFront_data={ "currentWeights": currentWeights, "paretoGraph": paretoGraph_points, "paretoTable": paretoTable_points}

    return paretoFront_data
#-------------------------------------------------------------------------------

class ParetoFrontGUI(QMainWindow):

    def __init__(self, paretoFront_data):
        super().__init__()
        self.setWindowTitle("Pareto Front GUI")
        self.setGeometry(100, 100, 1200, 720)
        self.paretoFront_data = paretoFront_data
        self.setup_ui()
#-------------------------------------------------------------------------------
    def setup_ui(self):
        # Create main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)  # Main layout is vertical

        # Setup the "Current Trade-off" section (upper_layout)
        tradeoff_layout = QVBoxLayout()
        title = QLabel("Current Trade-off")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 14, QFont.Bold))
        tradeoff_layout.addWidget(title)

        tradeoff_horizontal_layout = QHBoxLayout()  # Use QHBoxLayout for side-by-side layout

        # Pareto front plot setup
        # plt.style.use('seaborn')   # Matplotlib pre-defined style -old version
        plt.style.use('seaborn-v0_8') # Matplotlib pre-defined style -new version
        figure = Figure()
        self.canvas = FigureCanvas(figure)
        #self.canvas.setFixedHeight(380)

        # Adjust the layout
        self.canvas.figure.set_tight_layout(False)
        self.canvas.figure.subplots_adjust(bottom=0.15, top=0.95, left=0.1, right=0.95)

        self.plot = figure.add_subplot(111)
        self.cursor = None  # Initialize cursor attribute

        # Create QLabel for weights of current utility
        self.currentWeights_label = QLabel()
        self.currentWeights_label.setAlignment(Qt.AlignCenter)

        # Create Navigation toolbar for Pareto front plot
        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setIconSize(QSize(16, 16))

        # Layout for tradeoff graph, weights, and toolbar
        tradeoff_graph_layout = QVBoxLayout()
        tradeoff_graph_layout.addWidget(self.canvas)
        tradeoff_graph_layout.addWidget(self.currentWeights_label)
        tradeoff_graph_layout.addWidget(toolbar)

        # Define a custom UserRole for identifying cells with details
        self.DETAILS_ROLE = Qt.UserRole + 1

        # Create table widget for Pareto front data
        self.table = QTableWidget()

        # Setup the horizontal layout for the combo box used for sorting the table
        combo_layout = QHBoxLayout()
        sort_label = QLabel("Sort Table By:")
        sort_label.setFont(QFont("Arial", 12))
        self.sortComboBox = QComboBox()
        self.sortComboBox.addItems(["utility"] + list(objsSchema.keys()))
        self.sortComboBox.currentIndexChanged.connect(self.sortTable)
        combo_layout.addWidget(sort_label, 10)  # Smaller stretch factor for the label
        combo_layout.addWidget(self.sortComboBox, 90)  # Larger stretch factor for the combo box to fill the space

        # Layout for tradeoff table & sorting comboBox
        tradeoff_table_layout = QVBoxLayout()
        tradeoff_table_layout.addLayout(combo_layout)
        tradeoff_table_layout.addWidget(self.table)

        # Add graph layout and table layout to the horizontal layout
        tradeoff_horizontal_layout.addLayout(tradeoff_graph_layout, 50)  # 50% of the space for Plot on the left
        tradeoff_horizontal_layout.addLayout(tradeoff_table_layout, 50)  # 50% of the space for Table on the right

        # Add the horizontal layout to the tradeoff layout
        tradeoff_layout.addLayout(tradeoff_horizontal_layout)

        # Data setup for the "Current Trade-off" section
        # Plot Pareto front with initial data
        self.setup_graph()
        # Add the initial Utility weights to the Qlabel
        self.setup_weightsLabel()
        # Populate table with Pareto initial data
        self.setup_table()

        # Setup the "Best So Far" section (lower_layout)
        bestSoFar_layout = QVBoxLayout()
        title = QLabel("Best So Far")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 14, QFont.Bold))
        bestSoFar_layout.addWidget(title)

        # Create Best So Far table widget
        self.bestSoFar_table = QTableWidget()
        bestSoFar_layout.addWidget(self.bestSoFar_table)

        # Add upper and lower layouts to the main layout
        main_layout.addLayout(tradeoff_layout, 45)  # 45% of the space for the upper side
        main_layout.addLayout(bestSoFar_layout, 55)  # 55% of the space for the lower side

        self.statusBar()  # This initializes the status bar

#-------------------------------------------------------------------------------
    def setup_graph(self):
        # Deactivate existing cursor if it exists
        if self.cursor:
            self.cursor.remove()
            self.cursor = None

        xAxis = self.paretoFront_data["paretoGraph"].iloc[:, 0]
        yAxis = self.paretoFront_data["paretoGraph"].iloc[:, 1]

        # Use the first color of the Seaborn 'deep' palette
        seaborn_color = sns.color_palette("deep")[0]

        # Initialize all scatter points with seaborn_color
        self.scatter_colors = [seaborn_color] * len(xAxis)

        # Create scatter plot
        self.scatter = self.plot.scatter(xAxis, yAxis, facecolors=self.scatter_colors)

        self.plot.set_xlabel(self.paretoFront_data["paretoGraph"].columns[0], weight='bold', fontsize=11)
        self.plot.set_ylabel(self.paretoFront_data["paretoGraph"].columns[1], weight='bold', fontsize=11)
        self.plot.grid(True)

        # Create new cursor and attach it to the scatter plot (to handle click events on the scatter plot points)
        self.cursor = mplcursors.cursor(self.scatter, hover=False)
        self.cursor.connect("add", self.on_graphPoint_clicked)

        # Redraw the canvas
        self.canvas.draw_idle()

#-------------------------------------------------------------------------------
    def setup_weightsLabel(self):
        currentWeights_text = ' ,  '.join(f'<b> {obj}</b>: {round(self.paretoFront_data["currentWeights"][obj],3)}' for obj in self.paretoFront_data["currentWeights"])
        self.currentWeights_label.setText("<b style='color:#4C72B0;'> Weights of Current Utility: </b>" + currentWeights_text)

#-------------------------------------------------------------------------------
    def setup_table(self):
        # initially display one column in the table for the highest utility point
        self.table.setColumnCount(1)
        current_column_index = 0

        self.table.setRowCount(len(objsSchema)+4)  # 4 additional rows for : utility, solution, remove?, best?

        # Setup vertical headers
        vLabels = ["utility"]+[ obj for obj in objsSchema]+["Solution"]+["Remove?"]+["Best?"]
        self.table.setVerticalHeaderLabels(vLabels)

        max_utility_point = max(self.paretoFront_data["paretoTable"], key=lambda x: x["utility"])
        #max_utility_point_index = self.paretoFront_data["paretoTable"].index(max_utility_point)
        #print(max_utility_point_index)

        currentTable.append(max_utility_point)
        # Reset combo box index to default after sorting
        self.sortComboBox.setCurrentIndex(0)
        
        self.populate_table()

#-------------------------------------------------------------------------------
    def on_graphPoint_clicked(self, sel):
        # sel contains information about the clicked point
        pointIndex = sel.index  # This gets the array index of the clicked point in the paretoGraph data
        #print(pointindex)

        # Change the selected point color to red
        self.scatter_colors[pointIndex] = 'darkred'
        self.scatter.set_facecolors(self.scatter_colors)
        self.canvas.draw_idle()  # Redraw the scatter plot with the updated colors

        #current_column_index = self.table.columnCount()
        # Increase the column count to add a new column for the selected point
        #self.table.setColumnCount(current_column_index + 1)

        # Get the data of the clicked point from paretoTable_points
        point_data = self.paretoFront_data["paretoTable"][pointIndex]

        currentTable.append(point_data)
        # Sort the current table by utility as the default sorting option
        # This sorts the list of dictionaries based on the "utility" key in descending order
        currentTable.sort(key=lambda x: x["utility"], reverse=True)
        # Reset combo box index to default after sorting
        self.sortComboBox.setCurrentIndex(0)

        # update the table with data corresponding to that index
        self.populate_table()

#-------------------------------------------------------------------------------
    def populate_table(self):

        # Setup column counts
        self.table.setColumnCount(len(currentTable))

        # Setup horizontal headers
        hLabels = ["Rec {}".format(i + 1) for i in range(len(currentTable))]
        self.table.setHorizontalHeaderLabels(hLabels)

        # Populate the current trade-off table
        for point in range(len(currentTable)):

            # Populate table with utility values
            item = QTableWidgetItem(str(round(currentTable[point]["utility"], 3)))
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, point, item)

            # Populate table with objective values
            for i, obj in enumerate(objsSchema):
                item = QTableWidgetItem(str(currentTable[point]["objectives"][obj]))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i+1, point, item)

            # Populate table with solution values
            item = QTableWidgetItem("Details")
            item.setTextAlignment(Qt.AlignCenter)
            fontU = QFont()
            fontU.setUnderline(True)
            item.setFont(fontU)
            item.setData(self.DETAILS_ROLE, True)  # Mark this item as having details
            input_data = currentTable[point]["input"]
            output_data = currentTable[point]["output"]
            combined_data = {**output_data, **input_data}  # Merge both dictionaries
            item.setData(Qt.UserRole, combined_data)
            self.table.setItem(self.table.rowCount()-3, point, item)

            try:
                self.table.cellClicked.disconnect(self.show_details_dialog)  # Attempt to disconnect the signal if any
            except TypeError:
                pass  # If the signal was not connected, ignore the error
            self.table.cellClicked.connect(self.show_details_dialog)  # Connect the cellClicked signal to the show_details_dialog slot

            # Remove >>>
            # Create a radio widget & button for the "Remove?" row
            radio_widget, radio_button = self.create_radioButton()

            # Add the radio widget to the table
            self.table.setCellWidget(self.table.rowCount()-2, point, radio_widget)

            # Connect the signal of the radio button to the slot: call the on_remove_button_clicked function with the index of the selected point in currentTable
            radio_button.clicked.connect(partial(self.on_remove_button_clicked, point, radio_button))

            # Best >>>
            # Create a radio widget & button for the "Best?" row
            radio_widget, radio_button = self.create_radioButton()

            # Add the radio widget to the table
            self.table.setCellWidget(self.table.rowCount()-1, point, radio_widget)

            # Connect the signal of the radio button to the slot: call the on_best_button_clicked function with the selected point data in currentTable
            radio_button.clicked.connect(partial(self.on_best_button_clicked, currentTable[point], radio_button))

        # Formatting >
        # Set horizontal and vertical header labels in bold
        fontB = QFont()
        fontB.setBold(True)
        for i in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(i).setFont(fontB)
        for i in range(self.table.rowCount()):
            self.table.verticalHeaderItem(i).setFont(fontB)
        # Resize the columns to fit the contents
        #self.table.resizeColumnsToContents()

#-------------------------------------------------------------------------------
    def sortTable(self):
        sort_index = self.sortComboBox.currentIndex()  # This gets the index of the selected item in the combo box
        sort_key = self.sortComboBox.currentText()  # This gets the selected text, e.g., "utility", "cost", etc.

        # Sort the currentTable list based on the selected attribute
        if sort_key == "utility":
            currentTable.sort(key=lambda x: x[sort_key], reverse=True)
        else:
            currentTable.sort(key=lambda x: x["norm_objectives"][sort_key], reverse=True)

        # Regenerate the table with sorted data
        self.populate_table()

#-------------------------------------------------------------------------------
    def show_details_dialog(self, row, col):

        # Determine which table was clicked
        if self.sender() == self.table:
            item = self.table.item(row, col)
        elif self.sender() == self.bestSoFar_table:
            item = self.bestSoFar_table.item(row, col)
        else:
            return  # Not a recognized sender

        if not item or not item.data(self.DETAILS_ROLE):
            return  # No item at this cell or not marked for details

        dictionary = item.data(Qt.UserRole)
        if not dictionary:
            return  # No data to show in the dialog

        # Create the dialog
        dialog = QDialog(self)
        layout = QVBoxLayout(dialog)
        dialog.setWindowTitle("Solution Details for the selected point")
        dialog.setFixedSize(400, 400)

        # Create a tree widget
        tree = QTreeWidget()
        layout.addWidget(tree)
        tree.setHeaderLabels(["Item", "value"])
        tree.setMinimumSize(300, 200)

        # Set initial column widths
        tree.setColumnWidth(0, 150)
        tree.setColumnWidth(1, 300)

        # Set the horizontal scroll bar
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Recursive function to populate the tree widget with the dictionary
        def add_dict_to_tree(parent_item, dictionary):
            for key, value in dictionary.items():
                child = QTreeWidgetItem(parent_item)
                child.setText(0, str(key))
                if isinstance(value, dict):
                    add_dict_to_tree(child, value)
                else:
                    child.setText(1, str(value))

        add_dict_to_tree(tree.invisibleRootItem(), dictionary)

        # Execute the dialog
        dialog.exec_()
#-------------------------------------------------------------------------------
    def on_remove_button_clicked(self, pointIndex, radioButton):

        if radioButton.isChecked():
            # Ask user for confirmation
            reply = QMessageBox.question(self, 'Confirm Removal', f'Are you sure you want to remove Rec#{pointIndex +1}?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                if 0 <= pointIndex < len(currentTable):
                    del currentTable[pointIndex]
                    self.populate_table()

                else:
                    QMessageBox.warning(self, 'Error', 'Invalid point!')

            radioButton.setChecked(False)

#-------------------------------------------------------------------------------
    def on_best_button_clicked(self, selected_point, radioButton):

        if radioButton.isChecked():
            # Extract data of the current axes and the point associated with the clicked button
            currentXaxis= self.paretoFront_data["paretoGraph"].columns[0]
            currentYaxis= self.paretoFront_data["paretoGraph"].columns[1]
            currentWeights = selected_point["weights"]

            # Ask user for confirmation
            reply = QMessageBox.question(self, 'Confirmation', 'Are you sure this selection is the best?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                selected_point["comment"]= "" # initialize a comment field to be used by the user if needed

                bestSoFar.append(selected_point)

                # Update the current utility for each point in the bestSoFar list:
                for point in bestSoFar:
                    point["utility"]=(round(sum([ point["norm_objectives"][obj] * currentWeights[obj] for obj in point["norm_objectives"] ])/ sum([currentWeights[obj] for obj in point["norm_objectives"]]),3))

                self.regenerate_bestsofar_table()

                # Update the Pareto Front GUI and system state
                paretoFront_newData = paretoOptimal(paretoDB, objsSchema, currentXaxis, currentYaxis, currentWeights)
                self.update_state(paretoFront_newData)

            else:
                # If the user selects "No", uncheck the radio button
                radioButton.setChecked(False)

#-------------------------------------------------------------------------------
    # Regenerate the entire bestsofar table each time a new "Best So Far" point added
    def regenerate_bestsofar_table(self):

        # Setup column & row counts
        self.bestSoFar_table.setColumnCount(len(bestSoFar))
        self.bestSoFar_table.setRowCount(len(objsSchema)+7)  # 7 additional rows for : chart, utility, solution, comment?, Improve?, Remove?, Accept?

        # Setup horizontal headers
        hLabels = ["Best {}".format(i + 1) for i in range(len(bestSoFar))]
        self.bestSoFar_table.setHorizontalHeaderLabels(hLabels)

        # Setup vertical headers
        vLabels = ["Chart"]+["utility"]+[ obj for obj in objsSchema]+["Solution"]+["Comment?"]+["Improve?"]+["Remove?"]+["Accept?"]
        self.bestSoFar_table.setVerticalHeaderLabels(vLabels)

        # Populate the bestSoFar_table
        for point in range(len(bestSoFar)):

            # Populate table with bestSoFar charts (the first row)
            self.generateBarChart(point, bestSoFar[point])

            # Populate table with utility values
            item = QTableWidgetItem(str(round(bestSoFar[point]["utility"], 3)))
            item.setTextAlignment(Qt.AlignCenter)
            self.bestSoFar_table.setItem(1, point, item)

            # Populate table with objective values
            for i, obj in enumerate(objsSchema):
                item = QTableWidgetItem(str(bestSoFar[point]["objectives"][obj]))
                item.setTextAlignment(Qt.AlignCenter)
                self.bestSoFar_table.setItem(i+2, point, item)

            # Populate table with solution values
            item = QTableWidgetItem("Details")
            item.setTextAlignment(Qt.AlignCenter)
            fontU = QFont()
            fontU.setUnderline(True)
            item.setFont(fontU)
            item.setData(self.DETAILS_ROLE, True)  # Mark this item as having details
            input_data = bestSoFar[point]["input"]
            output_data = bestSoFar[point]["output"]
            combined_data = {**output_data, **input_data}  # Merge both dictionaries
            item.setData(Qt.UserRole, combined_data)
            self.bestSoFar_table.setItem(self.bestSoFar_table.rowCount()-5, point, item)

            try:
                self.bestSoFar_table.cellClicked.disconnect(self.show_details_dialog)  # Attempt to disconnect the signal if any
            except TypeError:
                pass  # If the signal was not connected, ignore the error
            self.bestSoFar_table.cellClicked.connect(self.show_details_dialog)  # Connect the cellClicked signal to the show_details_dialog slot

            # Comment >>>
            # Add editable QTableWidgetItem for user comments
            comment_item = QTableWidgetItem(bestSoFar[point]["comment"])
            comment_item.setTextAlignment(Qt.AlignCenter)
            comment_item.setForeground(QColor("darkblue"))
            comment_item.setFlags(comment_item.flags() | Qt.ItemIsEditable)
            self.bestSoFar_table.setItem(self.bestSoFar_table.rowCount()-4, point, comment_item)

            # Improve >>>
            # Create a radio widget & button for the "Improve?" row
            radio_widget, radio_button = self.create_radioButton()

            # Add this radio widget to the bestSoFar table
            self.bestSoFar_table.setCellWidget(self.bestSoFar_table.rowCount()-3, point, radio_widget)

            # Connect the signal of the radio button to the slot: call the improve_best_objective function with the selected point and the selected objective
            radio_button.clicked.connect(partial(self.improve_best_objective, point, radio_button))

            # Remove >>>
            # Create a radio widget & button for the "Remove?" row
            radio_widget, radio_button = self.create_radioButton()

            # Add this radio widget to the bestSoFar table
            self.bestSoFar_table.setCellWidget(self.bestSoFar_table.rowCount()-2, point, radio_widget)

            # Connect the signal of the radio button to the slot: call the remove_best function with the index of the selected point in bestSoFar
            radio_button.clicked.connect(partial(self.remove_best, point, radio_button))

            # Accept >>>
            # Create a radio widget & button for the "Accept?" row
            radio_widget, radio_button = self.create_radioButton()

            # Add this radio widget to the bestSoFar table
            self.bestSoFar_table.setCellWidget(self.bestSoFar_table.rowCount()-1, point, radio_widget)

            # Connect the signal of the radio button to the slot: call the accept_best function with the selected point
            radio_button.clicked.connect(partial(self.accept_best, point, radio_button))

        # Connect the itemChanged signal to on_comment_changed method
        self.bestSoFar_table.itemChanged.connect(self.on_comment_changed)

        # Resize the cols & rows to fit the contents
        self.bestSoFar_table.resizeColumnsToContents()
        self.bestSoFar_table.resizeRowsToContents()

#-------------------------------------------------------------------------------
    def generateBarChart(self, col, bestSoFar_point):

        # Create a canvas to display the bar chart in the first row of the point's column
        fig = Figure()
        ax = fig.add_subplot(111)
        canvas = FigureCanvas(fig)
        canvas.setFixedHeight(220)
        canvas.setFixedWidth(250)
        self.bestSoFar_table.setCellWidget(0, col, canvas)

        # Setup the bar chart
        categories = ["utility"] + list(bestSoFar_point["norm_objectives"].keys())
        values = [bestSoFar_point["utility"]] + list(bestSoFar_point["norm_objectives"].values())

        # Define a colormap and generate colors
        cmap = plt.colormaps['Blues'] # other options : 'Spectral', 'Set3'

        colors = cmap(np.linspace(0, 1, len(categories)))

        # Create the bar chart
        bars = ax.bar(categories, values, color=colors, width=0.25, edgecolor='black')

        # Add value labels on top of each bar
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), va='bottom')  # va: vertical alignment

        ax.set_ylim(0, 1.1)  # Slightly more than 1 to give space for labels
        #ax.set_ylabel('Normalized Value [0-1]', fontsize=8, fontweight='bold')
        ax.set_title('[0-1] Normalized Value', fontsize=8, fontweight='bold')
        #ax.set_title('Comparison of Objectives', fontsize=8, fontweight='bold')

        # Set keys positions and labels
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories)

#-------------------------------------------------------------------------------
    def on_comment_changed(self, item):

        column = item.column()
        row = item.row()
        comment_row_index = self.bestSoFar_table.rowCount() - 4  # 'Comment?' is the fourth-last row

        if row == comment_row_index:
            # Update the corresponding point's comment in the bestSoFar list
            bestSoFar[column]["comment"] = item.text()

#-------------------------------------------------------------------------------
    def improve_best_objective(self, pointIndex, radioButton):

        if radioButton.isChecked():

            pointData = bestSoFar[pointIndex]
            point_weights = pointData["weights"]

            current_row = self.bestSoFar_table.currentRow()

            if  1 < current_row <= len(objsSchema)+1 :       # -1=no selection, 0=chart row, 1=utility row, 2 to len(objsSchema)+1 = objective rows
                # A row is selected, proceed with fetching the row header text
                objective_name = self.bestSoFar_table.verticalHeaderItem(current_row).text()

                # Ask user for confirmation
                reply = QMessageBox.question(self, 'Confirm Removal', f'Are you sure you want to improve Best#{pointIndex +1} on the "{objective_name}" objective?',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

                if reply == QMessageBox.Yes:
                    # Call the paretoOptimal function with the point_weights and the selected objective
                    paretoFront_newData = paretoOptimal(paretoDB, objsSchema, "utility", objective_name, point_weights)

                    # update the Pareto Front GUI and system state
                    self.update_state(paretoFront_newData)

                    self.bestSoFar_table.setCurrentCell(-1, -1) # clear row selection

                    # provide feedback to the user
                    # QMessageBox.information(self, "Improvement Applied", f"Optimization for {objective_name} applied successfully.")

            else:
                # No valid objective row is selected, inform the user to select one
                QMessageBox.information(self, "Selection Required", "Please select first the row of the objective that you want to improve.")

            radioButton.setChecked(False)

#-------------------------------------------------------------------------------
    def remove_best(self, pointIndex, radioButton):

        if radioButton.isChecked():
            # Ask user for confirmation
            reply = QMessageBox.question(self, 'Confirm Removal', f'Are you sure you want to remove Best#{pointIndex +1}?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                if 0 <= pointIndex < len(bestSoFar):
                    del bestSoFar[pointIndex]

                    self.regenerate_bestsofar_table()

                    #QMessageBox.information(self, 'Removed', 'The point has been successfully removed.')
                else:
                    QMessageBox.warning(self, 'Error', 'Invalid point index.')

            radioButton.setChecked(False)

#-------------------------------------------------------------------------------
    def accept_best(self, pointIndex, radioButton):

        pointData = bestSoFar[pointIndex]

        if radioButton.isChecked():
            # Ask user for confirmation
            reply = QMessageBox.question(self, 'Confirm Removal', f'Are you sure you accept Best#{pointIndex +1} as your optimal recommendation?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                optimalRec["point"] = pointData
                self.bestSoFar_table.clear() # clear the current bestSoFar table
                self.generate_optimalRec_table()

            radioButton.setChecked(False)

#-------------------------------------------------------------------------------
    # Display only the accepted point in the bestsofar table
    def generate_optimalRec_table(self):

        # Setup column & row counts
        self.bestSoFar_table.setColumnCount(1)
        self.bestSoFar_table.setRowCount(len(objsSchema)+3)  # 3 additional rows for : chart, utility, solution

        # Setup horizontal headers
        hLabels = ["Optimal Recommendation"]
        self.bestSoFar_table.setHorizontalHeaderLabels(hLabels)

        # Setup vertical headers
        vLabels = ["Chart"]+["utility"]+[ obj for obj in objsSchema]+["Solution"]
        self.bestSoFar_table.setVerticalHeaderLabels(vLabels)

        # Populate table with chart (the first row)
        self.generateBarChart(0, optimalRec["point"])

        # Populate table with utility values
        item = QTableWidgetItem(str(round(optimalRec["point"]["utility"], 3)))
        item.setTextAlignment(Qt.AlignCenter)
        self.bestSoFar_table.setItem(1, 0, item)

        # Populate table with objective values
        for i, obj in enumerate(objsSchema):
            item = QTableWidgetItem(str(optimalRec["point"]["objectives"][obj]))
            item.setTextAlignment(Qt.AlignCenter)
            self.bestSoFar_table.setItem(i+2, 0, item)

        # Populate table with solution values
        item = QTableWidgetItem("Details")
        item.setTextAlignment(Qt.AlignCenter)
        fontU = QFont()
        fontU.setUnderline(True)
        item.setFont(fontU)
        item.setData(self.DETAILS_ROLE, True)  # Mark this item as having details
        input_data = optimalRec["point"]["input"]
        output_data = optimalRec["point"]["output"]
        combined_data = {**output_data, **input_data}  # Merge both dictionaries
        item.setData(Qt.UserRole, combined_data)
        self.bestSoFar_table.setItem(self.bestSoFar_table.rowCount()-1, 0, item)

        try:
            self.bestSoFar_table.cellClicked.disconnect(self.show_details_dialog)  # Attempt to disconnect the signal if any
        except TypeError:
            pass  # If the signal was not connected, ignore the error
        self.bestSoFar_table.cellClicked.connect(self.show_details_dialog)  # Connect the cellClicked signal to the show_details_dialog slot

        # Resize the cols & rows to fit the contents
        self.bestSoFar_table.resizeColumnsToContents()
        self.bestSoFar_table.resizeRowsToContents()

#-------------------------------------------------------------------------------
    def create_radioButton(self):
        # Create a widget to hold the radio button with appropriate styling
        radio_widget = QWidget()
        radio_layout = QHBoxLayout(radio_widget)
        radio_layout.setAlignment(Qt.AlignCenter)
        radio_layout.setContentsMargins(0, 0, 0, 0)

        # Initialize the radio button and add it to the layout
        radio_button = QRadioButton()
        radio_layout.addWidget(radio_button)
        radio_widget.setLayout(radio_layout)

        # Set the background color of the widget for better visibility
        radio_widget.setStyleSheet("background-color: lightgray;")

        # Return both the widget and the radio button for further manipulation
        return radio_widget, radio_button

#-------------------------------------------------------------------------------
    def update_state(self, paretoFront_newData):

        self.paretoFront_data=paretoFront_newData
        systemState.append(paretoFront_newData)

        # update Pareto graph
        self.plot.clear() # clear the old plot
        self.setup_graph()

        # update Current Weights label
        self.setup_weightsLabel()

        # update Pareto Table
        self.table.clear() # clear the old table
        currentTable.clear()
        self.setup_table()

        # Display a message in the status bar
        self.statusBar().showMessage("Pareto front data has been updated successfully.", 10000)  # Message displays for 10 seconds

        # Use a message box to inform the user
        #QMessageBox.information(self, "Update Successful", "Pareto front data has been updated successfully.")
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    # Initialization
    currentWeights =  { obj: 1/len(objsSchema) for obj in objsSchema}
    #currentWeights =  {'cost': 0.923860397184827, 'co2': 0.20285975728920072, 'manufTime': 0.32454565994026213}
    paretoFront_data = paretoOptimal(paretoDB, objsSchema,"utility", initialObj, currentWeights)
    #paretoFront_data = paretoOptimal(paretoDB, objsSchema,"aggr_coverage", "cost", currentWeights)
    #paretoFront_data = paretoOptimal(paretoDB, objsSchema,"cost", "co2", currentWeights)
    systemState.append(paretoFront_data)

    # Create Qt application
    app = QApplication(sys.argv)

    # Create main window and show
    main_window = ParetoFrontGUI(paretoFront_data)
    main_window.show()

    # Start event loop
    sys.exit(app.exec_())
#-------------------------------------------------------------------------------
