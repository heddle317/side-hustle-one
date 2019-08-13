from uuid import uuid4
import os
import traceback

from app import db
from app import log
from app import config
from app.utils.cache import Cache
from app.utils.datetime_tools import format_date
from app.utils.datetime_tools import now_utc

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import class_mapper

Base = declarative_base()
unchanging_fields = ['uuid', 'created_at']


def get(model, distinct=None, **kwargs):
    sort_by = kwargs.pop('sort_by', 'created_at')
    desc = kwargs.pop('desc', True)

    items = db.session.query(model)
    items, kwargs = filter_list_items(model, items, kwargs)
    items = filter_items(items, kwargs)
    items = items_sort_by(model, items, sort_by, desc)
    try:
        return items.first()
    except BaseException:
        db.session.rollback()
        message = traceback.print_exc()
        log(message, level='error')
        return None


def count(model, **kwargs):
    items = get_list(model, raw=True, **kwargs)
    return items.count()


def get_list(model, raw=False, distinct=False, page=None, num_per_page=None, **kwargs):
    sort_by = kwargs.pop('sort_by', 'created_at')
    limit = kwargs.pop('limit', None)
    desc = kwargs.pop('desc', True)

    items = db.session.query(model)
    items, kwargs = filter_list_items(model, items, kwargs)
    items = filter_items(items, kwargs)
    items = items_sort_by(model, items, sort_by, desc)
    if page and num_per_page:
        items = items.offset((page - 1) * num_per_page).limit(num_per_page)
    else:
        items = items.limit(limit)

    if raw:
        return items
    items = items.all()
    return items


def query_model(model, distinct=False):
    items = db.session.query(model)
    return items


def filter_list_items(model, items, kwargs):
    list_keys = []
    for key, value in kwargs.items():
        if isinstance(value, list):
            field = getattr(model, key)
            if value:
                items = items.filter(field.in_(value))
            list_keys.append(key)
    for key in list_keys:
        kwargs.pop(key)
    return items, kwargs


def filter_items(items, kwargs):
    if kwargs:
        return items.filter_by(**kwargs)
    return items


def items_sort_by(model, items, sort_by, desc):
    if hasattr(model, sort_by):
        order_by = getattr(model, sort_by)
        if desc:
            items = items.order_by(order_by.desc().nullslast())
        else:
            items = items.order_by(order_by.asc().nullslast())
    return items


def save(obj, refresh=True):
    try:
        obj = db.session.merge(obj)
        db.session.commit()
    except BaseException:
        log(traceback.print_exc(), level='error')
        db.session.rollback()
        raise

    obj.uncache()
    if refresh:
        db.session.refresh(obj)

    return obj


def delete(obj, hard_delete=False):
    obj.uncache()
    try:
        db.session.delete(obj)
        db.session.commit()
    except BaseException:
        log(traceback.print_exc(), level='error')
        db.session.rollback()
        raise


def update(obj, data):
    changed = False

    model = obj.__class__

    columns = model.__columns__() + model.__writeable_properties__()
    for field, val in data.items():
        if field not in columns:
            msg = "{}.update(): '{}' is not a column or property on {}".format(model.__name__, field, model.__name__)  # NOQA
            if config.UNIT_TESTING:
                raise Exception(msg)
            else:
                log(msg, level="error")
            continue
        if field not in unchanging_fields:
            setattr(obj, field, val)
            changed = True
    if changed:
        if hasattr(model, 'updated_at') and 'updated_at' not in data:
            obj.updated_at = now_utc()
        return save(obj)
    return obj


def create(model, **kwargs):
    """
    User.create(field1=value1,...)
    You can pass in any columns defined on the model as well as any
    settable properties:
        class Author(Base, BaseModelObject):
            uuid = Column(UUID, primary_key=True)
            name = Column(String)
        class BlogPost(Base, BaseModelObject):
            text = Column(String)
            author_uuid = Column(UUID)
            @property
            def author_name(self):
                author = Author.get(uuid=self.author_uuid)
                if author:
                    return author.name
            @author_name.setter
            def author_name(self, value):
                author = Author.get(name=value)
                if author:
                    self.author_uuid = author.uuid
        author = Author.create(name="kate")
        blog_post = BlogPost.create(text="insightful", author_name="kate")
        assert blog_post.author_uuid == author.uuid
        If there is a `slug` column defined on the model class then it
        will be auto-populated as a parameterized form of the `name`
        column
    """
    m = model()
    if hasattr(m, 'uuid'):
        m.uuid = str(uuid4())
    if hasattr(m, 'created_at'):
        m.created_at = now_utc()
    if hasattr(m, 'updated_at'):
        m.updated_at = now_utc()

    field_names = model.__columns__() + model.__writeable_properties__()
    for key, value in kwargs.items():
        if key not in field_names:
            msg = "{}.create(): '{}' is not a column or writeable property on {}".format(
                model.__name__, key, model.__name__)
            if config.UNIT_TESTING:
                raise Exception(msg)
            else:
                log(msg, level="error")
            continue
        setattr(m, key, value)

    return save(m, refresh=True)


class BaseModelObject(object):

    @classmethod
    def __columns__(cls):
        """Properties specified as columns on the class"""
        return [col.key for col in class_mapper(cls).iterate_properties]

    @classmethod
    def __readable_properties__(cls):
        """
        Properties specified via `@property` with a setter. Read-only
        properties are ommitted here because this code is used to filter
        **kwargs for create/update/etc.
        """
        parent_properties = []
        if hasattr(cls, '__bases__'):
            for base in cls.__bases__:
                if hasattr(base, '__readable_properties__'):
                    parent_properties += base.__readable_properties__()

        return [
            # Return just the name of the attributes
            keyvalue[0] for keyvalue in cls.__dict__.items()
            # An attribute that has the '.fget' is a property
            # and a '.fget' of not None is actually settable
            if hasattr(keyvalue[1], 'fget') and keyvalue[1].fget
        ] + parent_properties

    @classmethod
    def __writeable_properties__(cls):
        """
        Properties specified via `@property` with a setter. Read-only
        properties are ommitted here because this code is used to filter
        **kwargs for create/update/etc.
        """
        parent_properties = []
        if hasattr(cls, '__bases__'):
            for base in cls.__bases__:
                if hasattr(base, '__writeable_properties__'):
                    parent_properties += base.__writeable_properties__()

        return [
            # Return just the name of the attributes
            keyvalue[0] for keyvalue in cls.__dict__.items()
            # An attribute that has the '.fset' is a property
            # and a '.fset' of not None is actually settable
            if hasattr(keyvalue[1], 'fset') and keyvalue[1].fset
        ] + parent_properties

    def to_dict(self):
        attr_dict = {}
        for column_name in self.__class__.__columns__():
            attr_dict[column_name] = getattr(self, column_name)
        if hasattr(self, 'created_at'):
            attr_dict['created_at'] = format_date(self.created_at, '%a, %d %b %Y %H:%M:%S')
        if hasattr(self, 'updated_at'):
            attr_dict['updated_at'] = format_date(self.updated_at, '%a, %d %b %Y %H:%M:%S')
        return attr_dict

    @classmethod
    def count(cls, dead=False, **kwargs):
        if hasattr(cls, 'dead'):
            return count(cls, dead=dead, **kwargs)
        return count(cls, **kwargs)

    @classmethod
    def get_list(cls, dead=False, **kwargs):
        if hasattr(cls, 'dead'):
            return get_list(cls, dead=dead, **kwargs)
        else:
            return get_list(cls, **kwargs)

    @classmethod
    def paginate(cls, page, num_per_page, dead=False, **kwargs):
        if hasattr(cls, 'dead'):
            return get_list(cls, page=page, num_per_page=num_per_page, dead=dead, **kwargs)
        else:
            return get_list(cls, page=page, num_per_page=num_per_page, **kwargs)

    @classmethod
    def get(cls, dead=False, **kwargs):
        if kwargs.get('uuid'):
            item = Cache.get(kwargs.get('uuid'), obj_type=cls.__name__)
            if item:
                return item
        if hasattr(cls, 'dead'):
            return get(cls, dead=dead, **kwargs)
        else:
            return get(cls, **kwargs)

    @classmethod
    def get_or_404(cls, dead=False, **kwargs):
        from flask import abort
        item = cls.get(dead=dead, **kwargs)
        if not item:
            abort(404)
        return item

    @classmethod
    def create(cls, **kwargs):
        item = create(cls, **kwargs)
        return item

    @classmethod
    def get_or_create(cls, dead=False, **kwargs):
        if hasattr(cls, 'dead'):
            item = get(cls, dead=dead, **kwargs)
        else:
            item = get(cls, **kwargs)
        if not item:
            item = create(cls, **kwargs)
        return item

    @classmethod
    def delete_all(cls, dead=False, **kwargs):
        if hasattr(cls, 'dead'):
            items = get_list(cls, dead=dead, **kwargs)
        else:
            items = get_list(cls, **kwargs)
        for item in items:
            item.delete()

    @classmethod
    def truncate(cls):
        """
        Only for use in tests. Friggin' dangerous.
        This bypasses the `dead` column.
        """
        if os.environ.get('UNIT_TESTING'):
            db.session.query(cls).delete()
        else:
            raise Exception("Truncate method called in non-test environment")

    def update(self, **kwargs):
        item = update(self, kwargs)
        return item

    def delete(self):
        if hasattr(self, 'dead'):
            update(self, {'dead': True})
        else:
            delete(self)

    def cache(self):
        Cache.set(self.uuid, self, self.__class__.__name__)
        return self

    def uncache(self):
        Cache.delete(self.uuid, obj_type=self.__class__.__name__)

    def __repr__(self):
        cols = {col: getattr(self, col) for col in self.__class__.__columns__()}
        return "<{} {}>".format(self.__class__.__name__, cols)


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement,
                          parameters, context, executemany):
    import time
    conn.info.setdefault('query_start_time', []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement,
                         parameters, context, executemany):
    import time
    total = time.time() - conn.info['query_start_time'].pop(-1)
    if total > 1:
        log("Slow query (%f): %s", (total, statement))