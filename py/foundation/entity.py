"""Entity types."""
import json

from dataclasses import asdict, dataclass, fields
from itertools import chain
from typing import Dict, Generic, Iterable, Optional, Tuple, Type

from ._instantiate import _instantiate
from .geometry import BBox
from .ocr import InputWord
from .typing_utils import assert_exhaustive, unwrap


@dataclass(frozen=True)
class Entity:
  bbox: BBox

  @property
  def height(self) -> float:
    return self.bbox.height

  @property
  def width(self) -> float:
    return self.bbox.width

  @property
  def children(self) -> Iterable['Entity']:
    """Yields all sub-entities of this entity.

    See implementing subclass methods for entity-specific definitions.
    Can be seen as returning the adjacent entities in a document's Entity
    DAG.

    This method CANNOT call words().
    """
    raise NotImplementedError

  def entity_words(self) -> Iterable['Word']:
    """Yields all Word entities among this entity's children.

    Can be seen as returning an iterator over the leaves of this
    Entity's DAG.

    If this Entity is a Word, yields itself.

    STRONGLY RECOMMENDED not to override this.
    """
    yield from chain.from_iterable(E.entity_words() for E in self.children)

  @property
  def entity_text(self) -> Optional[str]:
    entity_fields = (field.name for field in fields(self))
    return self.text if 'text' in entity_fields else None # type: ignore # how to??


@dataclass(frozen=True)
class Page(Entity):
  """A Page is defined by an image region, or region in a document.

  Its bounding box is its dimensions, translated by its offset within the
  document. For example, a document with 3 pages, each 50x100, "stacking"
  pages on top of each other would put page 2's bbox as:
      top_left: (0, 100), bottom_right: (50, 200)
  """
  index: int
  type: str = 'Page'

  @property
  def children(self) -> Iterable['Entity']:
    """A page has no children.

    It is simply a region.
    """
    yield from []


@dataclass(frozen=True)
class Word(Entity):
  text: str
  origin: Optional[InputWord] = None
  type: str = 'Word'

  @staticmethod
  def from_input_word(origin: InputWord) -> 'Word':
    text = origin.text or ''
    return Word(origin.bbox, text, origin)

  @property
  def children(self) -> Iterable[Entity]:
    """Words have no children."""
    yield from []

  def entity_words(self) -> Iterable['Word']:
    """Yields itself.

    This provides the base case for Entity.words.
    """
    yield self


@dataclass(frozen=True)
class Text(Entity):
  """A sequence of one or more contiguous words."""
  text: str
  words: Tuple[Word, ...]
  maximality_score: Optional[float] = None
  ocr_score: Optional[float] = None
  type: str = 'Text'

  @staticmethod
  def from_words(
    words: Tuple[Word, ...],
    maximality_score: Optional[float] = None,
    ocr_score: Optional[float] = None) \
      -> 'Text':
    if not all(isinstance(word, Word) for word in words):
      raise ValueError('Text must be built from Words')
    bbox = unwrap(BBox.union(word.bbox for word in words))
    text = ' '.join(word.text for word in words)
    return Text(bbox, text, words, maximality_score, ocr_score)

  @property
  def children(self) -> Iterable[Word]:
    yield from self.words


@dataclass(frozen=True)
class Cluster(Entity):
  text: str
  lines: Tuple[Text, ...]
  label: Optional[str] = None
  type: str = 'Cluster'

  @staticmethod
  def from_phrases(phrases: Tuple[Text, ...]) -> 'Cluster':
    text = '\n'.join(phrase.text for phrase in phrases)
    bbox = unwrap(BBox.union(phrase.bbox for phrase in phrases))
    return Cluster(bbox, text, phrases)

  @property
  def children(self) -> Iterable[Text]:
    """A Cluster's children are phrases that it spans."""
    yield from self.lines


@dataclass(frozen=True)
class Date(Entity):
  text: str
  words: Tuple[Word, ...]
  likeness_score: Optional[float] = None
  type: str = 'Date'

  @property
  def children(self) -> Iterable[Entity]:
    """A Date's children are the words it spans."""
    yield from self.words


@dataclass(frozen=True)
class DollarAmount(Entity):
  text: str
  words: Tuple[Word, ...]
  units: Optional[str] = None
  likeness_score: Optional[float] = None
  type: str = 'DollarAmount'

  @property
  def children(self) -> Iterable[Entity]:
    """A DollarAmount's children are the words it spans."""
    yield from self.words


@dataclass(frozen=True)
class TableCell(Entity):
  content: Tuple[Entity, ...]
  type: str = 'TableCell'

  @property
  def children(self) -> Iterable[Entity]:
    """A TableCell's children are its contents."""
    yield from self.content


@dataclass(frozen=True)
class TableRow(Entity):
  cells: Tuple[TableCell, ...]
  type: str = 'TableRow'

  @property
  def children(self) -> Iterable[TableCell]:
    """A TableRow's children are its cells."""
    yield from self.cells


@dataclass(frozen=True)
class Table(Entity):
  rows: Tuple[TableRow, ...]
  type: str = 'Table'

  @property
  def children(self) -> Iterable[TableRow]:
    """A Table's children are its rows."""
    yield from self.rows


@dataclass(frozen=True)
class Number(Entity):
  words: Tuple[Word, ...]
  value: Optional[float] = None
  type: str = 'Number'

  @property
  def text(self) -> str:
    return str(self.value) if self.value else ''

  @property
  def children(self) -> Iterable[Entity]:
    """A Number's children are the words it spans."""
    yield from self.words


@dataclass(frozen=True)
class Integer(Entity):
  words: Tuple[Word, ...]
  value: Optional[int] = None
  type: str = 'Number'

  @property
  def text(self) -> str:
    return str(self.value) if self.value else ''

  @property
  def children(self) -> Iterable[Entity]:
    """An Integer's children are the words it spans."""
    yield from self.words


@dataclass(frozen=True)
class Time(Entity):
  words: Tuple[Word, ...]
  value: Optional[int] = None
  likeness_score: Optional[float] = None
  type: str = 'Time'

  @property
  def text(self) -> str:
    return str(self.value) if self.value else ''

  @property
  def children(self) -> Iterable[Entity]:
    """A Time's children are the words it spans."""
    yield from self.words


@dataclass(frozen=True)
class PersonName(Entity):
  text: str
  name_parts: Tuple[Text, ...]
  likeness_score: Optional[float] = None
  type: str = 'PersonName'

  @property
  def children(self) -> Iterable[Text]:
    """A PersonName's children are the phrases of its name parts."""
    yield from self.name_parts


@dataclass(frozen=True)
class Address(Entity):
  text: str
  lines: Tuple[Text, ...]
  address_parts: Tuple[Tuple[str, str], ...]
  likeness_score: Optional[float] = None
  type: str = 'Address'

  @property
  def children(self) -> Iterable[Text]:
    """An Address's children are the phrases it's composed of."""
    yield from self.lines


@dataclass(frozen=True)
class NamedEntity(Entity):
  text: str
  words: Tuple[Word, ...]
  value: Optional[str] = None
  label: Optional[str] = None
  type: str = 'NamedEntity'

  @property
  def children(self) -> Iterable[Entity]:
    """An entities children are the words it spans."""
    yield from self.words


"""
Associates a string entity type name to a custom class that inherits from
Entity.
"""
CustomEntityRegistry = Dict[str, Type[Entity]]


entity_registry = {
  'Address': Address,
  'Cluster': Cluster,
  'Date': Date,
  'DollarAmount': DollarAmount,
  'Integer': Integer,
  'NamedEntity': NamedEntity,
  'Number': Number,
  'Page': Page,
  'PersonName': PersonName,
  'Text': Text,
  'Table': Table,
  'TableCell': TableCell,
  'TableRow': TableRow,
  'Time': Time,
  'Word': Word,
}


def load_entity_from_json(blob: Dict) -> Entity:
  return _instantiate(Entity, blob, entity_registry)


def dump_to_json(entity: Entity) -> str:
  return json.dumps(asdict(entity), indent=2, sort_keys=True)
