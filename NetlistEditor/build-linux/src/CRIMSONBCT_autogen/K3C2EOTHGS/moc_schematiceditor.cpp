/****************************************************************************
** Meta object code from reading C++ file 'schematiceditor.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../../../src/gui/editor/schematiceditor.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'schematiceditor.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_qsapecng__SchematicEditor_t {
    QByteArrayData data[31];
    char stringdata0[341];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__SchematicEditor_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__SchematicEditor_t qt_meta_stringdata_qsapecng__SchematicEditor = {
    {
QT_MOC_LITERAL(0, 0, 25), // "qsapecng::SchematicEditor"
QT_MOC_LITERAL(1, 26, 11), // "stackEditor"
QT_MOC_LITERAL(2, 38, 0), // ""
QT_MOC_LITERAL(3, 39, 16), // "SchematicEditor*"
QT_MOC_LITERAL(4, 56, 6), // "editor"
QT_MOC_LITERAL(5, 63, 18), // "aboutToCloseEditor"
QT_MOC_LITERAL(6, 82, 12), // "dirtyChanged"
QT_MOC_LITERAL(7, 95, 5), // "dirty"
QT_MOC_LITERAL(8, 101, 9), // "fileSaved"
QT_MOC_LITERAL(9, 111, 8), // "fileName"
QT_MOC_LITERAL(10, 120, 10), // "fileLoaded"
QT_MOC_LITERAL(11, 131, 6), // "solved"
QT_MOC_LITERAL(12, 138, 4), // "save"
QT_MOC_LITERAL(13, 143, 6), // "saveAs"
QT_MOC_LITERAL(14, 150, 13), // "writeSimFiles"
QT_MOC_LITERAL(15, 164, 8), // "saveFile"
QT_MOC_LITERAL(16, 173, 8), // "loadFile"
QT_MOC_LITERAL(17, 182, 5), // "solve"
QT_MOC_LITERAL(18, 188, 5), // "reset"
QT_MOC_LITERAL(19, 194, 15), // "fileNameChanged"
QT_MOC_LITERAL(20, 210, 8), // "finished"
QT_MOC_LITERAL(21, 219, 12), // "stateChanged"
QT_MOC_LITERAL(22, 232, 16), // "Qt::WindowStates"
QT_MOC_LITERAL(23, 249, 8), // "oldState"
QT_MOC_LITERAL(24, 258, 8), // "newState"
QT_MOC_LITERAL(25, 267, 11), // "showUserDef"
QT_MOC_LITERAL(26, 279, 15), // "SchematicScene&"
QT_MOC_LITERAL(27, 295, 5), // "scene"
QT_MOC_LITERAL(28, 301, 12), // "cleanChanged"
QT_MOC_LITERAL(29, 314, 5), // "clean"
QT_MOC_LITERAL(30, 320, 20) // "externalCleanChanged"

    },
    "qsapecng::SchematicEditor\0stackEditor\0"
    "\0SchematicEditor*\0editor\0aboutToCloseEditor\0"
    "dirtyChanged\0dirty\0fileSaved\0fileName\0"
    "fileLoaded\0solved\0save\0saveAs\0"
    "writeSimFiles\0saveFile\0loadFile\0solve\0"
    "reset\0fileNameChanged\0finished\0"
    "stateChanged\0Qt::WindowStates\0oldState\0"
    "newState\0showUserDef\0SchematicScene&\0"
    "scene\0cleanChanged\0clean\0externalCleanChanged"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__SchematicEditor[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
      20,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       6,       // signalCount

 // signals: name, argc, parameters, tag, flags
       1,    1,  114,    2, 0x06 /* Public */,
       5,    0,  117,    2, 0x06 /* Public */,
       6,    1,  118,    2, 0x06 /* Public */,
       8,    1,  121,    2, 0x06 /* Public */,
      10,    1,  124,    2, 0x06 /* Public */,
      11,    0,  127,    2, 0x06 /* Public */,

 // slots: name, argc, parameters, tag, flags
      12,    0,  128,    2, 0x0a /* Public */,
      13,    0,  129,    2, 0x0a /* Public */,
      14,    0,  130,    2, 0x0a /* Public */,
      15,    1,  131,    2, 0x0a /* Public */,
      16,    1,  134,    2, 0x0a /* Public */,
      17,    0,  137,    2, 0x0a /* Public */,
      18,    0,  138,    2, 0x08 /* Private */,
      19,    1,  139,    2, 0x08 /* Private */,
      20,    0,  142,    2, 0x08 /* Private */,
      21,    2,  143,    2, 0x08 /* Private */,
      25,    1,  148,    2, 0x08 /* Private */,
      28,    1,  151,    2, 0x08 /* Private */,
      28,    0,  154,    2, 0x28 /* Private | MethodCloned */,
      30,    0,  155,    2, 0x08 /* Private */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Bool,    7,
    QMetaType::Void, QMetaType::QString,    9,
    QMetaType::Void, QMetaType::QString,    9,
    QMetaType::Void,

 // slots: parameters
    QMetaType::Bool,
    QMetaType::Bool,
    QMetaType::Bool,
    QMetaType::Bool, QMetaType::QString,    9,
    QMetaType::Bool, QMetaType::QString,    9,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::QString,    9,
    QMetaType::Void,
    QMetaType::Void, 0x80000000 | 22, 0x80000000 | 22,   23,   24,
    QMetaType::Void, 0x80000000 | 26,   27,
    QMetaType::Void, QMetaType::Bool,   29,
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

void qsapecng::SchematicEditor::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<SchematicEditor *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->stackEditor((*reinterpret_cast< SchematicEditor*(*)>(_a[1]))); break;
        case 1: _t->aboutToCloseEditor(); break;
        case 2: _t->dirtyChanged((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 3: _t->fileSaved((*reinterpret_cast< const QString(*)>(_a[1]))); break;
        case 4: _t->fileLoaded((*reinterpret_cast< const QString(*)>(_a[1]))); break;
        case 5: _t->solved(); break;
        case 6: { bool _r = _t->save();
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 7: { bool _r = _t->saveAs();
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 8: { bool _r = _t->writeSimFiles();
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 9: { bool _r = _t->saveFile((*reinterpret_cast< const QString(*)>(_a[1])));
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 10: { bool _r = _t->loadFile((*reinterpret_cast< const QString(*)>(_a[1])));
            if (_a[0]) *reinterpret_cast< bool*>(_a[0]) = std::move(_r); }  break;
        case 11: _t->solve(); break;
        case 12: _t->reset(); break;
        case 13: _t->fileNameChanged((*reinterpret_cast< const QString(*)>(_a[1]))); break;
        case 14: _t->finished(); break;
        case 15: _t->stateChanged((*reinterpret_cast< Qt::WindowStates(*)>(_a[1])),(*reinterpret_cast< Qt::WindowStates(*)>(_a[2]))); break;
        case 16: _t->showUserDef((*reinterpret_cast< SchematicScene(*)>(_a[1]))); break;
        case 17: _t->cleanChanged((*reinterpret_cast< bool(*)>(_a[1]))); break;
        case 18: _t->cleanChanged(); break;
        case 19: _t->externalCleanChanged(); break;
        default: ;
        }
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        switch (_id) {
        default: *reinterpret_cast<int*>(_a[0]) = -1; break;
        case 0:
            switch (*reinterpret_cast<int*>(_a[1])) {
            default: *reinterpret_cast<int*>(_a[0]) = -1; break;
            case 0:
                *reinterpret_cast<int*>(_a[0]) = qRegisterMetaType< SchematicEditor* >(); break;
            }
            break;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (SchematicEditor::*)(SchematicEditor * );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicEditor::stackEditor)) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (SchematicEditor::*)();
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicEditor::aboutToCloseEditor)) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (SchematicEditor::*)(bool );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicEditor::dirtyChanged)) {
                *result = 2;
                return;
            }
        }
        {
            using _t = void (SchematicEditor::*)(const QString & );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicEditor::fileSaved)) {
                *result = 3;
                return;
            }
        }
        {
            using _t = void (SchematicEditor::*)(const QString & );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicEditor::fileLoaded)) {
                *result = 4;
                return;
            }
        }
        {
            using _t = void (SchematicEditor::*)();
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&SchematicEditor::solved)) {
                *result = 5;
                return;
            }
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::SchematicEditor::staticMetaObject = { {
    QMetaObject::SuperData::link<QMdiSubWindow::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__SchematicEditor.data,
    qt_meta_data_qsapecng__SchematicEditor,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *qsapecng::SchematicEditor::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::SchematicEditor::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__SchematicEditor.stringdata0))
        return static_cast<void*>(this);
    return QMdiSubWindow::qt_metacast(_clname);
}

int qsapecng::SchematicEditor::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QMdiSubWindow::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 20)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 20;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 20)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 20;
    }
    return _id;
}

// SIGNAL 0
void qsapecng::SchematicEditor::stackEditor(SchematicEditor * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void qsapecng::SchematicEditor::aboutToCloseEditor()
{
    QMetaObject::activate(this, &staticMetaObject, 1, nullptr);
}

// SIGNAL 2
void qsapecng::SchematicEditor::dirtyChanged(bool _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 2, _a);
}

// SIGNAL 3
void qsapecng::SchematicEditor::fileSaved(const QString & _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 3, _a);
}

// SIGNAL 4
void qsapecng::SchematicEditor::fileLoaded(const QString & _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 4, _a);
}

// SIGNAL 5
void qsapecng::SchematicEditor::solved()
{
    QMetaObject::activate(this, &staticMetaObject, 5, nullptr);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
