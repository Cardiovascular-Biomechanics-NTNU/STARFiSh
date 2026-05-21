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

  QPalette palette;
  palette.setColor(QPalette::Window, QColor(32, 34, 37));
  palette.setColor(QPalette::WindowText, QColor(232, 234, 237));
  palette.setColor(QPalette::Base, QColor(24, 26, 29));
  palette.setColor(QPalette::AlternateBase, QColor(39, 42, 46));
  palette.setColor(QPalette::ToolTipBase, QColor(232, 234, 237));
  palette.setColor(QPalette::ToolTipText, QColor(24, 26, 29));
  palette.setColor(QPalette::Text, QColor(232, 234, 237));
  palette.setColor(QPalette::Button, QColor(56, 60, 66));
  palette.setColor(QPalette::ButtonText, QColor(232, 234, 237));
  palette.setColor(QPalette::BrightText, QColor(255, 255, 255));
  palette.setColor(QPalette::Link, QColor(86, 156, 214));
  palette.setColor(QPalette::Highlight, QColor(74, 136, 204));
  palette.setColor(QPalette::HighlightedText, QColor(255, 255, 255));
  palette.setColor(QPalette::Disabled, QPalette::Text, QColor(156, 163, 175));
  palette.setColor(QPalette::Disabled, QPalette::ButtonText, QColor(156, 163, 175));
  palette.setColor(QPalette::Disabled, QPalette::WindowText, QColor(156, 163, 175));

  app.setPalette(palette);
  app.setStyleSheet(
    "QMenuBar, QMenu, QToolBar, QStatusBar {"
    "  background: #202225;"
    "  color: #f1f3f4;"
    "}"
    "QMenuBar::item:selected, QMenu::item:selected {"
    "  background: #3f4854;"
    "}"
    "QToolBar {"
    "  border-bottom: 1px solid #4b5563;"
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
    "QTreeView, QTreeWidget, QTableView, QListView {"
    "  background: #202328;"
    "  alternate-background-color: #2b2f35;"
    "  color: #f1f3f4;"
    "  gridline-color: #4b5563;"
    "}"
    "QTreeView::item, QTreeWidget::item {"
    "  color: #f1f3f4;"
    "}"
    "QTreeView::item:selected, QTreeWidget::item:selected {"
    "  background: #4a88cc;"
    "  color: #ffffff;"
    "}"
    "QHeaderView::section {"
    "  background: #3b4149;"
    "  color: #ffffff;"
    "  border: 1px solid #5b6470;"
    "  padding: 2px 4px;"
    "}"
    "QTabBar::tab {"
    "  background: #252930;"
    "  color: #f1f3f4;"
    "  border: 1px solid #4b5563;"
    "  padding: 4px 10px;"
    "}"
    "QTabBar::tab:selected {"
    "  background: #313741;"
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
