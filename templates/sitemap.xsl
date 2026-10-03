<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:sm="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:xhtml="http://www.w3.org/1999/xhtml">
    <xsl:output method="html" encoding="UTF-8"/>
    <xsl:template match="/">
        <html>
        <head>
            <title>Wulver XML Sitemap</title>
            <meta name="viewport" content="width=device-width, initial-scale=1"/>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 32px; color: #172033; background: #f5f7fb; }
                main { max-width: 1200px; margin: 0 auto; }
                h1 { margin: 0 0 8px; font-size: 28px; }
                p { margin: 0 0 24px; color: #5d6678; }
                table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(20, 30, 50, .08); }
                th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #e8ebf1; vertical-align: top; }
                th { background: #eef2f8; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; }
                td { font-size: 14px; }
                a { color: #1769d2; text-decoration: none; overflow-wrap: anywhere; }
                .alternates { margin-top: 6px; color: #6d7585; font-size: 12px; }
            </style>
        </head>
        <body>
        <main>
            <h1>XML Sitemap</h1>
            <p>This sitemap is generated automatically by Wulver CMS.</p>
            <table>
                <thead>
                <tr>
                    <th>URL</th>
                    <th>Last modified</th>
                    <th>Priority</th>
                </tr>
                </thead>
                <tbody>
                <xsl:for-each select="sm:urlset/sm:url">
                    <tr>
                        <td>
                            <a href="{sm:loc}"><xsl:value-of select="sm:loc"/></a>
                            <xsl:if test="xhtml:link">
                                <div class="alternates">
                                    <xsl:for-each select="xhtml:link">
                                        <xsl:value-of select="@hreflang"/>: <xsl:value-of select="@href"/><br/>
                                    </xsl:for-each>
                                </div>
                            </xsl:if>
                        </td>
                        <td><xsl:value-of select="sm:lastmod"/></td>
                        <td><xsl:value-of select="sm:priority"/></td>
                    </tr>
                </xsl:for-each>
                <xsl:for-each select="sm:sitemapindex/sm:sitemap">
                    <tr>
                        <td><a href="{sm:loc}"><xsl:value-of select="sm:loc"/></a></td>
                        <td><xsl:value-of select="sm:lastmod"/></td>
                        <td>—</td>
                    </tr>
                </xsl:for-each>
                </tbody>
            </table>
        </main>
        </body>
        </html>
    </xsl:template>
</xsl:stylesheet>
