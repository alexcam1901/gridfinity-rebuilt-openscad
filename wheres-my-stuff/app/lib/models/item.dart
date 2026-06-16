class Item {
  final String id;
  final String name;
  final int quantity;
  final List<String> tags;
  final String? locationId;
  final String? ocrText;
  final String? gridfinityRef;
  final String? primaryPhotoId;

  const Item({
    required this.id,
    required this.name,
    this.quantity = 1,
    this.tags = const [],
    this.locationId,
    this.ocrText,
    this.gridfinityRef,
    this.primaryPhotoId,
  });

  Item copyWith({
    String? id,
    String? name,
    int? quantity,
    List<String>? tags,
    String? locationId,
    String? ocrText,
    String? gridfinityRef,
    String? primaryPhotoId,
  }) =>
      Item(
        id: id ?? this.id,
        name: name ?? this.name,
        quantity: quantity ?? this.quantity,
        tags: tags ?? this.tags,
        locationId: locationId ?? this.locationId,
        ocrText: ocrText ?? this.ocrText,
        gridfinityRef: gridfinityRef ?? this.gridfinityRef,
        primaryPhotoId: primaryPhotoId ?? this.primaryPhotoId,
      );
}
