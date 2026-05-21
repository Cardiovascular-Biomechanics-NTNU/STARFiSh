/****************************************************************************
** Meta object code from reading C++ file 'configpage.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../../../src/gui/configdialog/configpage.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'configpage.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_qsapecng__ConfigPage_t {
    QByteArrayData data[1];
    char stringdata0[21];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__ConfigPage_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__ConfigPage_t qt_meta_stringdata_qsapecng__ConfigPage = {
    {
QT_MOC_LITERAL(0, 0, 20) // "qsapecng::ConfigPage"

    },
    "qsapecng::ConfigPage"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__ConfigPage[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       0,    0, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

       0        // eod
};

void qsapecng::ConfigPage::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    Q_UNUSED(_o);
    Q_UNUSED(_id);
    Q_UNUSED(_c);
    Q_UNUSED(_a);
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::ConfigPage::staticMetaObject = { {
    QMetaObject::SuperData::link<QWidget::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__ConfigPage.data,
    qt_meta_data_qsapecng__ConfigPage,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *qsapecng::ConfigPage::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::ConfigPage::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__ConfigPage.stringdata0))
        return static_cast<void*>(this);
    return QWidget::qt_metacast(_clname);
}

int qsapecng::ConfigPage::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QWidget::qt_metacall(_c, _id, _a);
    return _id;
}
struct qt_meta_stringdata_qsapecng__GeneralPage_t {
    QByteArrayData data[5];
    char stringdata0[51];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__GeneralPage_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__GeneralPage_t qt_meta_stringdata_qsapecng__GeneralPage = {
    {
QT_MOC_LITERAL(0, 0, 21), // "qsapecng::GeneralPage"
QT_MOC_LITERAL(1, 22, 11), // "changeColor"
QT_MOC_LITERAL(2, 34, 0), // ""
QT_MOC_LITERAL(3, 35, 2), // "id"
QT_MOC_LITERAL(4, 38, 12) // "levelChanged"

    },
    "qsapecng::GeneralPage\0changeColor\0\0"
    "id\0levelChanged"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__GeneralPage[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       2,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    1,   24,    2, 0x08 /* Private */,
       4,    0,   27,    2, 0x08 /* Private */,

 // slots: parameters
    QMetaType::Void, QMetaType::Int,    3,
    QMetaType::Void,

       0        // eod
};

void qsapecng::GeneralPage::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<GeneralPage *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->changeColor((*reinterpret_cast< int(*)>(_a[1]))); break;
        case 1: _t->levelChanged(); break;
        default: ;
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::GeneralPage::staticMetaObject = { {
    QMetaObject::SuperData::link<ConfigPage::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__GeneralPage.data,
    qt_meta_data_qsapecng__GeneralPage,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *qsapecng::GeneralPage::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::GeneralPage::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__GeneralPage.stringdata0))
        return static_cast<void*>(this);
    return ConfigPage::qt_metacast(_clname);
}

int qsapecng::GeneralPage::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = ConfigPage::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 2)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 2;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 2)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 2;
    }
    return _id;
}
struct qt_meta_stringdata_qsapecng__FontPage_t {
    QByteArrayData data[3];
    char stringdata0[39];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_qsapecng__FontPage_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_qsapecng__FontPage_t qt_meta_stringdata_qsapecng__FontPage = {
    {
QT_MOC_LITERAL(0, 0, 18), // "qsapecng::FontPage"
QT_MOC_LITERAL(1, 19, 18), // "currentFontChanged"
QT_MOC_LITERAL(2, 38, 0) // ""

    },
    "qsapecng::FontPage\0currentFontChanged\0"
    ""
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_qsapecng__FontPage[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       1,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags
       1,    0,   19,    2, 0x08 /* Private */,

 // slots: parameters
    QMetaType::Void,

       0        // eod
};

void qsapecng::FontPage::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<FontPage *>(_o);
        Q_UNUSED(_t)
        switch (_id) {
        case 0: _t->currentFontChanged(); break;
        default: ;
        }
    }
    Q_UNUSED(_a);
}

QT_INIT_METAOBJECT const QMetaObject qsapecng::FontPage::staticMetaObject = { {
    QMetaObject::SuperData::link<ConfigPage::staticMetaObject>(),
    qt_meta_stringdata_qsapecng__FontPage.data,
    qt_meta_data_qsapecng__FontPage,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *qsapecng::FontPage::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *qsapecng::FontPage::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_qsapecng__FontPage.stringdata0))
        return static_cast<void*>(this);
    return ConfigPage::qt_metacast(_clname);
}

int qsapecng::FontPage::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = ConfigPage::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 1)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 1;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 1)
            *reinterpret_cast<int*>(_a[0]) = -1;
        _id -= 1;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
