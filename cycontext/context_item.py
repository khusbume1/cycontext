class ConTextItem:
    """An ConTextItem defines a ConText modifier. It defines the phrase to be matched,
    the category/semantic class, and the rule which the modifier executes.
    """
    _ALLOWED_RULES = ("FORWARD", "BACKWARD", "BIDIRECTIONAL", "TERMINATE", "MAX_TARGETS", "MAX_SCOPE")
    _ALLOWED_KEYS = {"literal", "rule", "pattern", "category", "metadata", "allowed_types", "filtered_types"}
    def __init__(self, literal, category, rule="BIDIRECTIONAL", pattern=None, allowed_types=None, excluded_types=None,
                 max_targets=None, max_scope=None, metadata=None):
        """Create an ConTextItem object.

        literal (str): The actual string of a concept. If pattern is None,
            this string will be lower-cased and matched to the lower-case string.
        category (str): The semantic class of the item.
        pattern (list or None): A spaCy pattern to match using token attributes.
            See https://spacy.io/usage/rule-based-matching.
        rule (str): The directionality or action of a modifier.
            One of ("forward", "backward", "bidirectional", or "terminate").
        allowed_types (set or None): A set of target labels to allow a modifier to modify.
            If None, will apply to any type not specifically excluded in excluded_types.
            Only one of allowed_types and excluded_types can be used. An error will be thrown
            if both or not None.
        excluded_types (set or None): A set of target labels which this modifier cannot modify.
            If None, will apply to all target types unless allowed_types is not None.
        max_targets (int or None): The maximum number of targets which a modifier can modify.
            If None, will modify all targets in its scope.
        max_scope (int or None): A number to explicitly limit the size of the modifier's scope
        metadata (dict or None): A dict of additional data to pass in,
            such as free-text comments, additional attributes, or ICD-10 codes.
            Default None.
        RETURNS (ConTextItem)
        """
        self.literal = literal.lower()
        self.category = category.upper()
        self.pattern = pattern
        self.rule = rule.upper()

        if allowed_types is not None and excluded_types is not None:
            raise ValueError("A ConTextItem was instantiated with non-null values for both allowed_types and excluded_types. "
                             "Only one of these can be non-null, since cycontext either explicitly includes or excludes target types.")
        if allowed_types is not None:
            self.allowed_types = {label.upper() for label in allowed_types}
        else:
            self.allowed_types = None
        if excluded_types is not None:
            self.excluded_types = {label.upper() for label in excluded_types}
        else:
            self.excluded_types = None

        if max_targets is not None and max_targets <= 0:
            raise ValueError("max_targets must be >= 0 or None.")
        self.max_targets = max_targets
        if max_scope is not None and max_scope <= 0:
            raise ValueError("max_scope must be >= 0 or None.")
        self.max_scope = max_scope

        self.metadata = metadata


        if self.rule not in self._ALLOWED_RULES:
            raise ValueError("Rule {0} not recognized. Must be one of: {1}".format(self.rule, self._ALLOWED_RULES))

    @classmethod
    def from_json(cls, filepath):
        """Read in a lexicon of modifiers from a JSON file.

        filepath (text): the .json file containing modifier rules

        RETURNS context_item (list): a list of ConTextItem objects
        RAISES KeyError if the dictionary contains any keys other than
            those accepted by ConTextItem.__init__
        """
        import json
        with open(filepath) as f:
            modifier_data = json.load(f)
        item_data = []
        for data in modifier_data["item_data"]:
            item_data.append(ConTextItem.from_dict(data))
        return item_data

    @classmethod
    def from_dict(cls, d):
        try:
            item = ConTextItem(**d)
        except TypeError:
            keys = set(d.keys())
            invalid_keys = keys.difference(cls._ALLOWED_KEYS)
            msg = ("JSON object contains invalid keys: {0}.\n"
                   "Must be one of: {1}".format(invalid_keys, cls._ALLOWED_KEYS))
            raise ValueError(msg)

        return item

    @classmethod
    def to_json(cls, item_data, filepath):
        import json
        data = {"item_data": [item.to_dict() for item in item_data]}
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)

    def to_dict(self):
        d = {}
        for key in self._ALLOWED_KEYS:
            d[key] = self.__dict__.get(key)
        return d

    def __repr__(self):
        return f"ConTextItem(literal='{self.literal}', category='{self.category}', pattern={self.pattern}, rule='{self.rule}')"




