/****************************************************************************
** Meta object code from reading C++ file 'workplane.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../../../src/gui/workplane/workplane.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'workplane.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_qsapecng__MarkableCurve_t {
    QByteArrayData data[6];
    char stringdata0[53];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__MarkableCurve_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__MarkableCurve_t qt_meta_stringdata_qsapecng__MarkableCurve = {
    {
QT_MOC_LITERAL(0, 0, 23), // "qsapecng::MarkableCurve"
QT_MOC_LITERAL(1, 24, 8), // "selected"
QT_MOC_LITERAL(2, 33, 0), // ""
QT_MOC_LITERAL(3, 34, 8), // "appended"
QT_MOC_LITERAL(4, 43, 3), // "pos"
QT_MOC_LITERAL(5, 47, 5) // "moved"

    },
    "qsapecng::MarkableCurve\0selected\0\0"
    "appended\0pos\0moved"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__MarkableCurve[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       3,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    0,   29,    2, 0x0a /* Public */,
       3,    1,   30,    2, 0x0a /* Public */,
       5,    1,   33,    2, 0x0a /* Public */,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void, QMetaType::QPointF,    4,
    QMetaType::Void, QMetaType::QPointF,    4,

       0        // eod
};

void qsapecng::MarkableCurve::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<MarkableCurve *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->selected(); break;
        case 1: _t->appended((*reinterpret_cast< const QPointF(*)>(_a[1]))); break;
        case 2: _t->moved((*reinterpret_cast< const QPointF(*)>(_a[1]))); break;
        default: ;
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::MarkableCurve::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__MarkableCurve.data,
    qt_meta_data_qsapecng__MarkableCurve,
    qt_static_metacall,
    nullptr,
    nullptr
} };


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
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 3;
    }
    return _id;
}
struct qt_meta_stringdata_qsapecng__WorkPlane_t {
    QByteArrayData data[10];
    char stringdata0[89];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__WorkPlane_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__WorkPlane_t qt_meta_stringdata_qsapecng__WorkPlane = {
    {
QT_MOC_LITERAL(0, 0, 19), // "qsapecng::WorkPlane"
QT_MOC_LITERAL(1, 20, 8), // "setDirty"
QT_MOC_LITERAL(2, 29, 0), // ""
QT_MOC_LITERAL(3, 30, 13), // "xAxisLogScale"
QT_MOC_LITERAL(4, 44, 3), // "log"
QT_MOC_LITERAL(5, 48, 13), // "yAxisLogScale"
QT_MOC_LITERAL(6, 62, 4), // "plot"
QT_MOC_LITERAL(7, 67, 12), // "WorkPlane::F"
QT_MOC_LITERAL(8, 80, 1), // "f"
QT_MOC_LITERAL(9, 82, 6) // "redraw"

    },
    "qsapecng::WorkPlane\0setDirty\0\0"
    "xAxisLogScale\0log\0yAxisLogScale\0plot\0"
    "WorkPlane::F\0f\0redraw"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__WorkPlane[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       8,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    0,   54,    2, 0x0a /* Public */,
       3,    1,   55,    2, 0x0a /* Public */,
       3,    0,   58,    2, 0x2a /* Public | MethodCloned */,
       5,    1,   59,    2, 0x0a /* Public */,
       5,    0,   62,    2, 0x2a /* Public | MethodCloned */,
       6,    1,   63,    2, 0x0a /* Public */,
       6,    1,   66,    2, 0x0a /* Public */,
       9,    0,   69,    2, 0x0a /* Public */,

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

void qsapecng::WorkPlane::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<WorkPlane *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->setDirty(); break;
        case 1: _t->xAxisLogScale((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 2: _t->xAxisLogScale(); break;
        case 3: _t->yAxisLogScale((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 4: _t->yAxisLogScale(); break;
        case 5: _t->plot((*reinterpret_cast< WorkPlane::F(*)>(_a[1]))); break;
        case 6: _t->plot((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 7: _t->redraw(); break;
        default: ;
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::WorkPlane::staticMetaObject = { {
    QMetaObject::SuperData::link<QWidget::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__WorkPlane.data,
    qt_meta_data_qsapecng__WorkPlane,
    qt_static_metacall,
    nullptr,
    nullptr
} };


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
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 8;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
