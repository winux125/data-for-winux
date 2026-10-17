/** Kazakh is not included in React Aria's bundled table/grid dictionaries. */
export const kazakhGridStrings = {
  deselectedItem: (args: { item: string }) => `${args.item}: таңдау алынды.`,
  select: "Таңдау",
  selectedCount: (args: { count: number }) => args.count === 0 ? "Таңдалған элементтер жоқ." : `${args.count} элемент таңдалды.`,
  selectedAll: "Барлық элементтер таңдалды.",
  selectedItem: (args: { item: string }) => `${args.item} таңдалды.`,
  longPressToSelect: "Таңдау режимін қосу үшін басып тұрыңыз.",
};

export const kazakhTableStrings = {
  select: "Таңдау", selectAll: "Барлығын таңдау", sortable: "сұрыпталатын баған",
  ascending: "өсу ретімен", descending: "кему ретімен",
  ascendingSort: (args: { columnName: string }) => `${args.columnName} бағаны бойынша өсу ретімен сұрыпталды`,
  descendingSort: (args: { columnName: string }) => `${args.columnName} бағаны бойынша кему ретімен сұрыпталды`,
  columnSize: (args: { value: number }) => `${args.value} пиксель`,
  resizerDescription: "Өлшемін өзгерту үшін Enter пернесін басыңыз",
  expand: "Жаю", collapse: "Жию",
};
