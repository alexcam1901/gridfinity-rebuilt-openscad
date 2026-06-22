class Location {
  final String id;
  final String name;
  final String type;
  final String? parentId;
  final String? notes;

  const Location({
    required this.id,
    required this.name,
    required this.type,
    this.parentId,
    this.notes,
  });

  Location copyWith({
    String? id,
    String? name,
    String? type,
    String? parentId,
    String? notes,
  }) =>
      Location(
        id: id ?? this.id,
        name: name ?? this.name,
        type: type ?? this.type,
        parentId: parentId ?? this.parentId,
        notes: notes ?? this.notes,
      );

  static const types = ['room', 'shelf', 'cabinet', 'drawer', 'bin', 'other'];
}
