/****************************************************************************
** Meta object code from reading C++ file 'workplane.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../../../src/gui/workplane/workplane.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'workplane.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_qsapecng__MarkableCurve_t {
    uint offsetsAndSizes[12];
    char stringdata0[24];
    char stringdata1[9];
    char stringdata2[1];
    char stringdata3[9];
    char stringdata4[4];
    char stringdata5[6];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_qsapecng__MarkableCurve_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_qsapecng__MarkableCurve_t qt_meta_stringdata_qsapecng__MarkableCurve = {
    {
        QT_MOC_LITERAL(0, 23),  // "qsapecng::MarkableCurve"
        QT_MOC_LITERAL(24, 8),  // "selected"
        QT_MOC_LITERAL(33, 0),  // ""
        QT_MOC_LITERAL(34, 8),  // "appended"
        QT_MOC_LITERAL(43, 3),  // "pos"
        QT_MOC_LITERAL(47, 5)   // "moved"
    },
    "qsapecng::MarkableCurve",
    "selected",
    "",
    "appended",
    "pos",
    "moved"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_qsapecng__MarkableCurve[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       3,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       1,    0,   32,    2, 0x0a,    1 /* Public */,
       3,    1,   33,    2, 0x0a,    2 /* Public */,
       5,    1,   36,    2, 0x0a,    4 /* Public */,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void, QMetaType::QPointF,    4,
    QMetaType::Void, QMetaType::QPointF,    4,

       0        // eod
};

Q_CONSTINIT const QMetaObject qsapecng::MarkableCurve::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__MarkableCurve.offsetsAndSizes,
    qt_meta_data_qsapecng__MarkableCurve,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_qsapecng__MarkableCurve_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<MarkableCurve, std::true_type>,
        // method 'selected'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'appended'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<const QPointF &, std::false_type>,
        // method 'moved'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<const QPointF &, std::false_type>
    >,
    nullptr
} };

void qsapecng::MarkableCurve::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<MarkableCurve *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->selected(); break;
        case 1: _t->appended((*reinterpret_cast< std::add_pointer_t<QPointF>>(_a[1]))); break;
        case 2: _t->moved((*reinterpret_cast< std::add_pointer_t<QPointF>>(_a[1]))); break;
        default: ;
        }
    }
}

const QMetaObject *qsapecng::MarkableCurve::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::MarkableCurve::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__MarkableCurve.stringdata0))
        return static_cast<void*>(this);
    if (!strcmp(_clname, "QwtPlotCurve"))
        return static_cast< QwtPlotCurve*>(this);
    return QObject::qt_metacast(_clname);
}

int qsapecng::MarkableCurve::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QObject::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 3)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 3;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 3)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 3;
    }
    return _id;
}
namespace {
struct qt_meta_stringdata_qsapecng__WorkPlane_t {
    uint offsetsAndSizes[20];
    char stringdata0[20];
    char stringdata1[9];
    char stringdata2[1];
    char stringdata3[14];
    char stringdata4[4];
    char stringdata5[14];
    char stringdata6[5];
    char stringdata7[13];
    char stringdata8[2];
    char stringdata9[7];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_qsapecng__WorkPlane_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_qsapecng__WorkPlane_t qt_meta_stringdata_qsapecng__WorkPlane = {
    {
        QT_MOC_LITERAL(0, 19),  // "qsapecng::WorkPlane"
        QT_MOC_LITERAL(20, 8),  // "setDirty"
        QT_MOC_LITERAL(29, 0),  // ""
        QT_MOC_LITERAL(30, 13),  // "xAxisLogScale"
        QT_MOC_LITERAL(44, 3),  // "log"
        QT_MOC_LITERAL(48, 13),  // "yAxisLogScale"
        QT_MOC_LITERAL(62, 4),  // "plot"
        QT_MOC_LITERAL(67, 12),  // "WorkPlane::F"
        QT_MOC_LITERAL(80, 1),  // "f"
        QT_MOC_LITERAL(82, 6)   // "redraw"
    },
    "qsapecng::WorkPlane",
    "setDirty",
    "",
    "xAxisLogScale",
    "log",
    "yAxisLogScale",
    "plot",
    "WorkPlane::F",
    "f",
    "redraw"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_qsapecng__WorkPlane[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       8,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       1,    0,   62,    2, 0x0a,    1 /* Public */,
       3,    1,   63,    2, 0x0a,    2 /* Public */,
       3,    0,   66,    2, 0x2a,    4 /* Public | MethodCloned */,
       5,    1,   67,    2, 0x0a,    5 /* Public */,
       5,    0,   70,    2, 0x2a,    7 /* Public | MethodCloned */,
       6,    1,   71,    2, 0x0a,    8 /* Public */,
       6,    1,   74,    2, 0x0a,   10 /* Public */,
       9,    0,   77,    2, 0x0a,   12 /* Public */,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void, QMetaType::Bool,    4,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Bool,    4,
    QMetaType::Void,
    QMetaType::Void, 0x80000000 | 7,    8,
    QMetaType::Void, QMetaType::Int,    8,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject qsapecng::WorkPlane::staticMetaObject = { {
    QMetaObject::SuperData::link<QWidget::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__WorkPlane.offsetsAndSizes,
    qt_meta_data_qsapecng__WorkPlane,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_qsapecng__WorkPlane_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<WorkPlane, std::true_type>,
        // method 'setDirty'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'xAxisLogScale'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<bool, std::false_type>,
        // method 'xAxisLogScale'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'yAxisLogScale'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<bool, std::false_type>,
        // method 'yAxisLogScale'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'plot'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<WorkPlane::F, std::false_type>,
        // method 'plot'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'redraw'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void qsapecng::WorkPlane::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<WorkPlane *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->setDirty(); break;
        case 1: _t->xAxisLogScale((*reinterpret_cast< std::add_pointer_t<bool>>(_a[1]))); break;
        case 2: _t->xAxisLogScale(); break;
        case 3: _t->yAxisLogScale((*reinterpret_cast< std::add_pointer_t<bool>>(_a[1]))); break;
        case 4: _t->yAxisLogScale(); break;
        case 5: _t->plot((*reinterpret_cast< std::add_pointer_t<WorkPlane::F>>(_a[1]))); break;
        case 6: _t->plot((*reinterpret_cast< std::add_pointer_t<int>>(_a[1]))); break;
        case 7: _t->redraw(); break;
        default: ;
        }
    }
}

const QMetaObject *qsapecng::WorkPlane::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::WorkPlane::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__WorkPlane.stringdata0))
        return static_cast<void*>(this);
    return QWidget::qt_metacast(_clname);
}

int qsapecng::WorkPlane::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QWidget::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 8)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 8;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 8)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 8;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
