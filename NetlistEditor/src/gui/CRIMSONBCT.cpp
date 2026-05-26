/*

	CRIMSON Boundary Condition Toolbox, graphical design and
	specification of boundary conditions for blood flow simulation.
	Copyright (C) 2015, King's College London <christopher.arthurs@kcl.ac.uk>.

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.

 This file incorporates work covered by the following copyright and
 permission notice:
    QSapecNG - Qt based SapecNG GUI front-end
    Copyright (C) 2009, Michele Caini

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/


#include "gui/qsapecngwindow.h"

#include <QApplication>
#include <QFont>
#include <QPalette>
#include <QSplashScreen>
#include <QPixmap>
#include <QStyleFactory>
#include <QTime>

#include <QMainWindow>

namespace
{
void applyDarkTheme(QApplication& app)
{
  app.setStyle(QStyleFactory::create("Fusion"));

  QFont font("DejaVu Sans");
  font.setStyleHint(QFont::SansSerif);
  font.setPointSize(10);
  app.setFont(font);

  QPalette palette;
  palette.setColor(QPalette::Window, QColor(43, 43, 43));
  palette.setColor(QPalette::WindowText, QColor(255, 255, 255));
  palette.setColor(QPalette::Base, QColor(25, 25, 25));
  palette.setColor(QPalette::AlternateBase, QColor(43, 43, 43));
  palette.setColor(QPalette::ToolTipBase, QColor(255, 255, 255));
  palette.setColor(QPalette::ToolTipText, QColor(18, 20, 23));
  palette.setColor(QPalette::Text, QColor(255, 255, 255));
  palette.setColor(QPalette::Button, QColor(43, 43, 43));
  palette.setColor(QPalette::ButtonText, QColor(255, 255, 255));
  palette.setColor(QPalette::BrightText, QColor(255, 255, 255));
  palette.setColor(QPalette::Link, QColor(99, 179, 237));
  palette.setColor(QPalette::Highlight, QColor(63, 131, 248));
  palette.setColor(QPalette::HighlightedText, QColor(255, 255, 255));
  palette.setColor(QPalette::Disabled, QPalette::Text, QColor(203, 213, 225));
  palette.setColor(QPalette::Disabled, QPalette::ButtonText, QColor(203, 213, 225));
  palette.setColor(QPalette::Disabled, QPalette::WindowText, QColor(203, 213, 225));

  app.setPalette(palette);
  app.setStyleSheet(
    "QWidget {"
    "  color: #ffffff;"
    "  font-family: \"DejaVu Sans\", \"Segoe UI\", \"Arial\", sans-serif;"
    "  font-size: 10pt;"
    "}"
    "QMenuBar, QMenu, QToolBar, QStatusBar {"
    "  background: #2b2b2b;"
    "  color: #ffffff;"
    "}"
    "QMenuBar::item:selected, QMenu::item:selected {"
    "  background: #3f83f8;"
    "  color: #ffffff;"
    "}"
    "QToolBar {"
    "  border-bottom: 1px solid #64748b;"
    "  spacing: 4px;"
    "}"
    "QToolButton {"
    "  background: #515861;"
    "  border: 1px solid #69717c;"
    "  border-radius: 3px;"
    "  padding: 2px;"
    "}"
    "QToolButton:hover {"
    "  background: #626b76;"
    "}"
    "QToolButton:pressed, QToolButton:checked {"
    "  background: #4078b8;"
    "}"
    "QLabel {"
    "  color: #ffffff;"
    "}"
    "QTreeView, QTreeWidget, QTableView, QListView {"
    "  background: #191919;"
    "  alternate-background-color: #2b2b2b;"
    "  color: #ffffff;"
    "  font-size: 10pt;"
    "  gridline-color: #64748b;"
    "}"
    "QTreeView::item, QTreeWidget::item {"
    "  color: #ffffff;"
    "}"
    "QTreeView::item:selected, QTreeWidget::item:selected {"
    "  background: #3f83f8;"
    "  color: #ffffff;"
    "}"
    "QHeaderView::section {"
    "  background: #3b4149;"
    "  color: #ffffff;"
    "  border: 1px solid #5b6470;"
    "  padding: 2px 4px;"
    "}"
    "QTabBar::tab {"
    "  background: #2b2b2b;"
    "  color: #ffffff;"
    "  border: 1px solid #64748b;"
    "  padding: 5px 12px;"
    "}"
    "QTabBar::tab:selected {"
    "  background: #2b2b2b;"
    "}"
  );
}
}


int main(int argc, char** argv)
{
  QApplication app(argc, argv);
  applyDarkTheme(app);

  QPixmap pixmap(":/images/CRIMSONBoundaryConditionToolboxLogo.png");
  QSplashScreen splash(pixmap, Qt::WindowStaysOnTopHint);

  splash.show();

/*
 ... // Loading some items
 splash->showMessage("Loaded modules");

 qApp->processEvents();

 ... // Establishing connections
 splash->showMessage("Established connections");

 qApp->processEvents();
*/

  qsapecng::QSapecNGWindow window;
  window.show();
  
  splash.finish(&window);

  return app.exec();
}
