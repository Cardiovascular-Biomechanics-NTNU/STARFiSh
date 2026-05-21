/****************************************************************************
** Meta object code from reading C++ file 'schematicscene.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../../../src/gui/editor/schematicscene.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'schematicscene.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_qsapecng__SchematicScene_t {
    QByteArrayData data[10];
    char stringdata0[122];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__SchematicScene_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__SchematicScene_t qt_meta_stringdata_qsapecng__SchematicScene = {
    {
QT_MOC_LITERAL(0, 0, 24), // "qsapecng::SchematicScene"
QT_MOC_LITERAL(1, 25, 11), // "showUserDef"
QT_MOC_LITERAL(2, 37, 0), // ""
QT_MOC_LITERAL(3, 38, 15), // "SchematicScene&"
QT_MOC_LITERAL(4, 54, 5), // "scene"
QT_MOC_LITERAL(5, 60, 15), // "propertyChanged"
QT_MOC_LITERAL(6, 76, 10), // "resetNodes"
QT_MOC_LITERAL(7, 87, 14), // "setGridVisible"
QT_MOC_LITERAL(8, 102, 7), // "visible"
QT_MOC_LITERAL(9, 110, 11) // "resetStatus"

    },
    "qsapecng::SchematicScene\0showUserDef\0"
    "\0SchematicScene&\0scene\0propertyChanged\0"
    "resetNodes\0setGridVisible\0visible\0"
    "resetStatus"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__SchematicScene[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       6,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       2,       // signalCount

 // signals: name, argc, parameters, tag, flags
       1,    1,   44,    2, 0x06 /* Public */,
       5,    0,   47,    2, 0x06 /* Public */,

 // slots: name, argc, parameters, tag, flags
       6,    0,   48,    2, 0x0a /* Public */,
       7,    1,   49,    2, 0x0a /* Public */,
       7,    0,   52,    2, 0x2a /* Public | MethodCloned */,
       9,    0,   53,    2, 0x0a /* Public */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void, QMetaType::Bool,    8,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

void qsapecng::SchematicScene::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<SchematicScene *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->showUserDef((*reinterpret_cast< SchematicScene(*)>(_a[1]))); break;
        case 1: _t->propertyChanged(); break;
        case 2: _t->resetNodes(); break;
        case 3: _t->setGridVisible((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 4: _t->setGridVisible(); break;
        case 5: _t->resetStatus(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (SchematicScene::*)(SchematicScene & );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicScene::showUserDef)) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (SchematicScene::*)();
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicScene::propertyChanged)) {
                *result = 1;
                return;
            }
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::SchematicScene::staticMetaObject = { {
    QMetaObject::SuperData::link<QGraphicsScene::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__SchematicScene.data,
    qt_meta_data_qsapecng__SchematicScene,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *qsapecng::SchematicScene::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::SchematicScene::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__SchematicScene.stringdata0))
        return static_cast<void*>(this);
    return QGraphicsScene::qt_metacast(_clname);
}

int qsapecng::SchematicScene::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QGraphicsScene::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 6)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 6;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 6)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 6;
    }
    return _id;
}

// SIGNAL 0
void qsapecng::SchematicScene::showUserDef(SchematicScene & _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void qsapecng::SchematicScene::propertyChanged()
{
    QMetaObject::activate(this, &staticMetaObject, 1, nullptr);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
