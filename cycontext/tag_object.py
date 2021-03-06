class TagObject:
    """Represents a concept found by ConText in a document.
    Is the result of ConTextItem matching a span of text in a Doc.
    """

    def __init__(self, context_item, start, end, doc):
        """Create a new TagObject from a document span.

        context_item (int): The ConTextItem object which defines the modifier.
        start (int): The start token index.
        end (int): The end token index (non-inclusive).
        doc (Doc): The spaCy Doc which contains this span.
        """
        self.context_item = context_item
        self.start = start
        self.end = end
        self.doc = doc

        self._targets = []
        self._num_targets = 0

        self._scope_start = None
        self._scope_end = None

        self.set_scope()

    @property
    def span(self):
        """The spaCy Span object, which is a view of self.doc, covered by this match."""
        return self.doc[self.start : self.end]

    @property
    def rule(self):
        """Returns the associated rule."""
        return self.context_item.rule

    @property
    def category(self):
        """Returns the associated category."""
        return self.context_item.category

    @property
    def scope(self):
        """Returns the associated scope."""
        return self.doc[self._scope_start : self._scope_end]

    @property
    def allowed_types(self):
        """Returns the associated allowed types."""
        return self.context_item.allowed_types

    @property
    def excluded_types(self):
        """Returns the associated excluded types."""
        return self.context_item.excluded_types

    @property
    def num_targets(self):
        """Returns the associated number of targets."""
        return self._num_targets

    @property
    def max_targets(self):
        """Returns the associated maximum number of targets."""
        return self.context_item.max_targets

    @property
    def max_scope(self):
        """Returns the associated maximum scope."""
        return self.context_item.max_scope

    def allows(self, target_label):
        """Returns True if a modifier is able to modify a target type.
        A modifier may not be allowed if either self.allowed_types is not None and
        target_label is not in it, or if self.excluded_types is not None and
        target_label is in it.
        """
        if self.allowed_types is not None:
            if target_label not in self.allowed_types:
                return False
            return True
        if self.excluded_types is not None:
            if target_label not in self.excluded_types:
                return True
            return False
        return True

    def set_scope(self):
        """Applies the rule of the ConTextItem which generated
        this TagObject to define a scope.
        If self.max_scope is None, then the default scope is the sentence which it occurs in
        in whichever direction defined by self.rule.
        For example, if the rule is "forward", the scope will be [self.end: sentence.end].
        If the rule is "backward", it will be [self.start: sentence.start].

        If self.max_scope is not None and the length of the default scope is longer than self.max_scope,
        it will be reduced to self.max_scope.


        """
        sent = self.doc[self.start].sent
        if sent is None:
            raise ValueError(
                "ConText failed because sentence boundaries have not been set. "
                "Add an upstream component such as the dependency parser, Sentencizer, or PyRuSH to detect sentence boundaries."
            )

        if self.rule.lower() == "forward":
            self._scope_start, self._scope_end = self.end, sent.end
            if (
                self.max_scope is not None
                and (self._scope_end - self._scope_start) > self.max_scope
            ):
                self._scope_end = self.end + self.max_scope

        elif self.rule.lower() == "backward":
            self._scope_start, self._scope_end = sent.start, self.start
            if (
                self.max_scope is not None
                and (self._scope_end - self._scope_start) > self.max_scope
            ):
                self._scope_start = self.start - self.max_scope
        else:  # bidirectional
            self._scope_start, self._scope_end = sent.start, sent.end

            # Set the max scope on either side
            # Backwards
            if (
                self.max_scope is not None
                and (self.start - self._scope_start) > self.max_scope
            ):
                self._scope_start = self.start - self.max_scope
            # Forwards
            if (
                self.max_scope is not None
                and (self._scope_end - self.end) > self.max_scope
            ):
                self._scope_end = self.end + self.max_scope

    def update_scope(self, span):
        """Change the scope of self to be the given spaCy span.

        span (Span): a spaCy Span which contains the scope
        which a modifier should cover.
        """
        self._scope_start, self._scope_end = span.start, span.end

    def limit_scope(self, other):
        """If self and obj have the same category
        or if obj has a directionality of 'terminate',
        use the span of obj to update the scope of self.
        Limiting the scope of two modifiers of the same category
        reduces the number of modifiers. For example, in
        'no evidence of CHF, no pneumonia', 'pneumonia' will only
        be modified by 'no', not 'no evidence of'.
        'terminate' modifiers limit the scope of a modifier
        like 'no evidence of' in 'no evidence of CHF, **but** there is pneumonia'

        other (TagObject)
        Returns True if obj modfified the scope of self
        """
        if self.span.sent != other.span.sent:
            return False
        if self.rule.upper() == "TERMINATE":
            return False
        # Check if the other modifier is a type which can modify self
        # or if they are the same category. If not, don't reduce scope.
        if (other.rule.upper() != "TERMINATE") and (other.category.upper() not in self.context_item.terminated_by) and (
            other.category.upper() != self.category.upper()
        ):
            return False

        # If two modifiers have the same category but modify different target types,
        # don't limit scope.
        if self.category == other.category and ((self.allowed_types != other.allowed_types) or (
            self.excluded_types != other.excluded_types)
        ):
            return False

        orig_scope = self.scope
        if self.rule.lower() in ("forward", "bidirectional"):
            if other > self:
                self._scope_end = min(self._scope_end, other.start)
        if self.rule.lower() in ("backward", "bidirectional"):
            if other < self:
                self._scope_start = max(self._scope_start, other.end)
        return orig_scope != self.scope

    def modifies(self, target):
        """Returns True if the target is within the modifier scope
        and self is allowed to modify target.

        target (Span): a spaCy span representing a target concept.
        """
        # If the target and modifier overlap, meaning at least one token
        # one extracted as both a target and modifier, return False
        # to avoid self-modifying concepts

        if self.overlaps_target(target):
            return False
        if self.rule == "TERMINATE":
            return False
        if not self.allows(target.label_.upper()):
            return False
        if target[0] in self.scope:
            return True
        if target[-1] in self.scope:
            return True
        return False

    def modify(self, target):
        """Add target to the list of self._targets and increment self._num_targets."""
        self._targets.append(target)
        self._num_targets += 1

    def reduce_targets(self):
        """If self.max_targets is not None, reduce the targets which are modified
        so that only the n closest targets are left. Distance is measured as
        the distance to either the start or end of a target (whichever is closer).
        """
        if self.max_targets is None or self.num_targets <= self.max_targets:
            return

        target_dists = []
        for target in self._targets:
            dist = min(abs(self.start - target.end), abs(target.start - self.end))
            target_dists.append((target, dist))
        srtd_targets, _ = zip(*sorted(target_dists, key=lambda x: x[1]))
        self._targets = srtd_targets[: self.max_targets]
        self._num_targets = len(self._targets)

    def overlaps(self, other):
        """ Returns whether the object overlaps with another span

        other (): the other object to check for overlaps

        RETURNS: true if there is overlap, false otherwise.
        """
        return (
            self.span[0] in other.span
            or self.span[-1] in other.span
            or other.span[0] in self.span
            or other.span[-1] in self.span
        )

    def overlaps_target(self, target):
        """Returns True if self overlaps with a spaCy span."""
        return (
            self.span[0] in target
            or self.span[-1] in target
            or target[0] in self.span
            or target[-1] in self.span
        )

    def __gt__(self, other):
        return self.span > other.span

    def __ge__(self, other):
        return self.span >= other.span

    def __lt__(self, other):
        return self.span < other.span

    def __le__(self, other):
        return self.span <= other.span

    def __len__(self):
        return len(self.span)

    def __repr__(self):
        return f"<TagObject> [{self.span}, {self.category}]"
