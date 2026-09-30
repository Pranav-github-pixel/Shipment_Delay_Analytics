Delay Distribution - SELECT Late_delivery_risk, COUNT(*) as count FROM shipments GROUP BY Late_delivery_risk
Delay Rate by Shipping Mode - SELECT `Shipping Mode`, AVG(Late_delivery_risk) as delay_rate, COUNT(*) as total_orders FROM shipments GROUP BY `Shipping Mode` ORDER BY delay_rate DESC
Top 10 Regions by Delay Rate - SELECT `Order Region`, AVG(Late_delivery_risk) as delay_rate FROM shipments GROUP BY `Order Region` ORDER BY delay_rate DESC LIMIT 10
Delay Rate by Speed Tier - SELECT `Shipping_Speed_Tier`, AVG(Late_delivery_risk) as delay_rate, COUNT(*) as order_count FROM shipments GROUP BY `Shipping_Speed_Tier` ORDER BY delay_rate DESC
Analytical Features - SELECT Shipping_Speed_Tier, Order_Volume_Tier, Order_Value_Segment, Weekend_Order, Late_delivery_risk FROM shipments LIMIT 10
