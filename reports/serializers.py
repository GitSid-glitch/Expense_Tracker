from rest_framework import serializers


class FinanceSummarySerializer(serializers.Serializer):
    currency = serializers.CharField()
    income = serializers.CharField()
    expense = serializers.CharField()
    investment = serializers.CharField()
    savings = serializers.CharField()
